#! /usr/bin/env python3
from plc import PlcTester

import uvicorn
import asyncio
import re
import os
import time
import json
import websocket
import threading
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, status
from fastapi.responses import FileResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from typing import Any


SERVICE_NAME = "PLC Extension"

app = FastAPI(
    title="PLC Extension API",
    description="API for the PLC extension",
)

logger.info(f"Starting {SERVICE_NAME}!")
tester = PlcTester()

# Global variables for background task
background_task = None

class WebSocketMAVLinkClient:
    def __init__(self, mavlink_host="ws://127.0.0.1/mavlink2rest/ws/mavlink?filter=SEND_ONLY", component_id=196):
        self.mavlink_host = mavlink_host
        self.vehicle_id = os.getenv("MAV_SYSTEM_ID", 1)
        self.component_id = component_id  # Using component ID 196 for PLC telemetry
        self.ws = None
        self.ws_connected = False
        
    def create_websocket_connection(self):
        """
        Create and manage websocket connection to mavlink2rest
        """
        try:
            logger.info(f"Connecting to WebSocket at {self.mavlink_host}")
            
            def on_open(ws):
                logger.info("WebSocket connection opened")
                self.ws_connected = True
            
            def on_close(ws, close_status_code, close_msg):
                logger.warning("WebSocket connection closed")
                self.ws_connected = False
                
            def on_error(ws, error):
                logger.error(f"WebSocket error: {error}")
                self.ws_connected = False
            
            # Create websocket connection
            self.ws = websocket.WebSocketApp(
                self.mavlink_host,
                on_open=on_open,
                on_close=on_close,
                on_error=on_error
            )
            
            # Start connection in a separate thread
            websocket_thread = threading.Thread(target=self.ws.run_forever)
            websocket_thread.daemon = True
            websocket_thread.start()
            
            # Wait for connection to establish
            timeout = 5.0
            start_time = time.time()
            while not self.ws_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            if not self.ws_connected:
                logger.error("Failed to establish WebSocket connection within timeout")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error creating WebSocket connection: {e}")
            return False
    
    def send_mavlink_message_ws(self, message_type: str, message_data: dict) -> bool:
        """
        Send a MAVLink message via websocket
        """
        if not self.ws_connected or not self.ws:
            logger.warning("WebSocket not connected, attempting to reconnect...")
            if not self.create_websocket_connection():
                return False
        
        try:
            # Create the message payload
            message = {
                "header": {
                    "system_id": self.vehicle_id,
                    "component_id": self.component_id,
                    "sequence": 0
                },
                "message": {
                    "type": message_type,
                    **message_data
                }
            }
            
            # Send via websocket
            self.ws.send(json.dumps(message))
            return True
            
        except Exception as e:
            logger.error(f"Error sending {message_type} via WebSocket: {e}")
            self.ws_connected = False
            return False
    
    def send_named_value_float(self, name, value, timestamp_us):
        """
        Send NAMED_VALUE_FLOAT message with quality metrics
        """
        # Convert name to 10-char list with null padding (MAVLink requirement)
        name_truncated = name[:10]  # Truncate to max 10 chars
        name_chars = list(name_truncated)  # Convert to list of characters
        name_chars.extend(['\u0000'] * (10 - len(name_chars)))  # Pad with null chars to 10 chars
        
        message_data = {
            "time_boot_ms": 0,  # Convert microseconds to milliseconds
            "name": name_chars,
            "value": value
        }
        
        return self.send_mavlink_message_ws("NAMED_VALUE_FLOAT", message_data)
    
    def close(self):
        """
        Close the WebSocket connection
        """
        if self.ws:
            try:
                self.ws.close()
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        self.ws_connected = False

# Initialize WebSocket MAVLink client
ws_mavlink_client = WebSocketMAVLinkClient()

# Network monitoring state
network_stats_prev = None
last_stats_time = None

class NetworkStats:
    def __init__(self, interface="eth0"):
        self.interface = interface
        
    def read_interface_stats(self):
        """Read network interface statistics from /proc/net/dev"""
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()
            
            for line in lines[2:]:  # Skip header lines
                if self.interface in line:
                    fields = line.split()
                    interface_name = fields[0].rstrip(':')
                    if interface_name == self.interface:
                        # Parse the statistics (bytes, packets, errs, drop, etc.)
                        rx_bytes = int(fields[1])
                        rx_packets = int(fields[2])
                        rx_errs = int(fields[3])
                        rx_drop = int(fields[4])
                        
                        tx_bytes = int(fields[9])
                        tx_packets = int(fields[10])
                        tx_errs = int(fields[11])
                        tx_drop = int(fields[12])
                        
                        return {
                            'rx_bytes': rx_bytes,
                            'rx_packets': rx_packets,
                            'rx_errs': rx_errs,
                            'rx_drop': rx_drop,
                            'tx_bytes': tx_bytes,
                            'tx_packets': tx_packets,
                            'tx_errs': tx_errs,
                            'tx_drop': tx_drop,
                            'timestamp': time.time()
                        }
            return None
        except Exception as e:
            logger.error(f"Error reading network stats: {e}")
            return None
    
    def calculate_rates_and_errors(self, current_stats, prev_stats):
        """Calculate rates and error percentages"""
        if not prev_stats or not current_stats:
            return None
            
        time_diff = current_stats['timestamp'] - prev_stats['timestamp']
        if time_diff <= 0:
            return None
            
        # Calculate byte rates (bytes per second)
        rx_rate = (current_stats['rx_bytes'] - prev_stats['rx_bytes']) / time_diff
        tx_rate = (current_stats['tx_bytes'] - prev_stats['tx_bytes']) / time_diff
        
        # Calculate packet rates
        rx_packet_rate = (current_stats['rx_packets'] - prev_stats['rx_packets']) / time_diff
        tx_packet_rate = (current_stats['tx_packets'] - prev_stats['tx_packets']) / time_diff
        
        # Calculate error counts (total errors in this interval)
        rx_errs_delta = current_stats['rx_errs'] - prev_stats['rx_errs']
        tx_errs_delta = current_stats['tx_errs'] - prev_stats['tx_errs']
        rx_drop_delta = current_stats['rx_drop'] - prev_stats['rx_drop']
        tx_drop_delta = current_stats['tx_drop'] - prev_stats['tx_drop']
        
        # Calculate error percentages
        total_rx_packets = current_stats['rx_packets'] - prev_stats['rx_packets']
        total_tx_packets = current_stats['tx_packets'] - prev_stats['tx_packets']
        
        rx_err_percent = (rx_errs_delta / max(total_rx_packets, 1)) * 100
        tx_err_percent = (tx_errs_delta / max(total_tx_packets, 1)) * 100
        rx_drop_percent = (rx_drop_delta / max(total_rx_packets, 1)) * 100
        tx_drop_percent = (tx_drop_delta / max(total_tx_packets, 1)) * 100
        
        return {
            'rx_rate_bps': rx_rate,
            'tx_rate_bps': tx_rate,
            'rx_packet_rate': rx_packet_rate,
            'tx_packet_rate': tx_packet_rate,
            'rx_errs_count': rx_errs_delta,
            'tx_errs_count': tx_errs_delta,
            'rx_drop_count': rx_drop_delta,
            'tx_drop_count': tx_drop_delta,
            'rx_err_percent': rx_err_percent,
            'tx_err_percent': tx_err_percent,
            'rx_drop_percent': rx_drop_percent,
            'tx_drop_percent': tx_drop_percent,
            'time_interval': time_diff
        }

network_monitor = NetworkStats("eth0")

async def post_named_value_float(name: str, value: float):
    """Post a named value float to MAVLink endpoint using WebSocket"""
    try:
        # Get current timestamp in microseconds
        timestamp_us = int(time.time() * 1e6)
        
        # Send via WebSocket using the new client
        success = ws_mavlink_client.send_named_value_float(name, value, timestamp_us)
        
        if not success:
            logger.warning(f"Failed to post {name}: {value} via WebSocket")
            
    except Exception as e:
        logger.error(f"Error posting {name} to MAVLink via WebSocket: {e}")

async def background_monitoring():
    """Background task to monitor rate and SNR every 5 seconds"""
    global network_stats_prev
    
    while True:
        try:
            # Get PLC rate data
            rates = tester.read_rates()
            if rates and len(rates) >= 2:
                tx_rate = float(rates[0])
                rx_rate = float(rates[1])
                await post_named_value_float("PlcTxRate", tx_rate)
                await post_named_value_float("PlcRxRate", rx_rate)

            # Get network interface statistics
            current_net_stats = network_monitor.read_interface_stats()
            if current_net_stats and network_stats_prev:
                # Calculate rates and error statistics
                net_metrics = network_monitor.calculate_rates_and_errors(current_net_stats, network_stats_prev)
                if net_metrics:
                    # Post network TX/RX rates (convert to Mbps for easier reading)
                    await post_named_value_float("EthTxMbs", net_metrics['tx_rate_bps'] / 1_000_000)
                    await post_named_value_float("EthRxMbs", net_metrics['rx_rate_bps'] / 1_000_000)
                    
                    # Post combined error and drop counts for this interval
                    tx_total_issues = net_metrics['tx_errs_count'] + net_metrics['tx_drop_count']
                    rx_total_issues = net_metrics['rx_errs_count'] + net_metrics['rx_drop_count']
                    await post_named_value_float("EthTxErr", float(tx_total_issues))
                    await post_named_value_float("EthRxErr", float(rx_total_issues))
                    
                    # Post combined error and drop percentages
                    tx_total_percent = net_metrics['tx_err_percent'] + net_metrics['tx_drop_percent']
                    rx_total_percent = net_metrics['rx_err_percent'] + net_metrics['rx_drop_percent']
                    await post_named_value_float("EthTxPct", tx_total_percent)
                    await post_named_value_float("EthRxPct", rx_total_percent)
                    
                    tx_total_issues = net_metrics['tx_errs_count'] + net_metrics['tx_drop_count']
                    rx_total_issues = net_metrics['rx_errs_count'] + net_metrics['rx_drop_count']

            # Update previous stats for next iteration
            if current_net_stats:
                network_stats_prev = current_net_stats
            
        except Exception as e:
            logger.error(f"Error in background monitoring: {e}")
        
        # Wait 5 seconds before next check
        await asyncio.sleep(5)


@app.get("/devices", status_code=status.HTTP_200_OK)
@version(1, 0)
async def detect_devices() -> Any:
  return tester.detect_devices()

@app.get("/tonemap", status_code=status.HTTP_200_OK)
@version(1, 0)
async def tonemap() -> Any:
  return tester.read_tonemap()


@app.get("/rate", status_code=status.HTTP_200_OK)
@version(1, 0)
async def get_rates() -> Any:
  return tester.read_rates()

@app.get("/snr", status_code=status.HTTP_200_OK)
@version(1, 0)
async def snr() -> Any:
  return tester.read_snr()

@app.get("/network", status_code=status.HTTP_200_OK)
@version(1, 0)
async def get_network_stats() -> Any:
  """Get current network interface statistics"""
  current_stats = network_monitor.read_interface_stats()
  if current_stats and network_stats_prev:
      metrics = network_monitor.calculate_rates_and_errors(current_stats, network_stats_prev)
      if metrics:
          tx_total_issues = metrics['tx_errs_count'] + metrics['tx_drop_count']
          rx_total_issues = metrics['rx_errs_count'] + metrics['rx_drop_count']
          tx_total_percent = metrics['tx_err_percent'] + metrics['tx_drop_percent']
          rx_total_percent = metrics['rx_err_percent'] + metrics['rx_drop_percent']
          
          return {
              "interface": "eth0",
              "tx_rate_mbps": metrics['tx_rate_bps'] / 1_000_000,
              "rx_rate_mbps": metrics['rx_rate_bps'] / 1_000_000,
              "tx_issues_count": tx_total_issues,
              "rx_issues_count": rx_total_issues,
              "tx_issue_percent": tx_total_percent,
              "rx_issue_percent": rx_total_percent,
              "time_interval": metrics['time_interval']
          }
  return {"error": "No network statistics available yet"}


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)

@app.on_event("startup")
async def startup_event():
    """Start the background monitoring task"""
    global background_task, network_stats_prev
    logger.info("Starting background monitoring task...")

    # Initialize WebSocket connection
    ws_mavlink_client.create_websocket_connection()

    # Initialize network stats
    network_stats_prev = network_monitor.read_interface_stats()

    background_task = asyncio.create_task(background_monitoring())
    logger.info("Background monitoring task started")

@app.on_event("shutdown")
async def shutdown_event():
    """Stop the background monitoring task"""
    global background_task
    logger.info("Shutting down background monitoring task...")
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            logger.info("Background task cancelled successfully")
            pass

    # Close WebSocket connection
    ws_mavlink_client.close()

    logger.info("Background monitoring task stopped")

app.mount("/", StaticFiles(directory="static",html = True), name="static")

@app.get("/", response_class=FileResponse)
async def root() -> Any:
        return "index.html"

if __name__ == "__main__":
    # Running uvicorn with log disabled so loguru can handle it
    uvicorn.run(app, host="0.0.0.0", port=1142, log_config=None)