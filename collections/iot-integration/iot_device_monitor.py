#!/usr/bin/env python3
"""
IoT Device Monitor and Integration Engine
Discovers, monitors, and processes data from IoT devices and edge computing nodes
"""

import asyncio
import json
import logging
import socket
import struct
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading
from enum import Enum

import requests
import ipaddress
from influxdb import InfluxDBClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeviceType(Enum):
    """IoT Device Types"""
    SMART_SWITCH = "smart_switch"
    SENSOR = "sensor" 
    CAMERA = "camera"
    THERMOSTAT = "thermostat"
    SMART_PLUG = "smart_plug"
    HUB = "hub"
    GATEWAY = "gateway"
    EDGE_COMPUTE = "edge_compute"
    UNKNOWN = "unknown"

class DeviceStatus(Enum):
    """Device Status States"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class IoTDevice:
    """IoT Device Information"""
    ip_address: str
    mac_address: str
    device_type: DeviceType
    manufacturer: str
    model: str
    firmware_version: str
    hostname: str
    last_seen: datetime
    status: DeviceStatus
    capabilities: List[str]
    metadata: Dict[str, Any]
    security_info: Dict[str, Any]
    energy_metrics: Dict[str, float]
    network_metrics: Dict[str, float]

@dataclass
class EdgeNode:
    """Edge Computing Node Information"""
    node_id: str
    ip_address: str
    hostname: str
    cpu_cores: int
    memory_gb: float
    storage_gb: float
    gpu_available: bool
    compute_capacity: float
    current_load: float
    services_running: List[str]
    last_heartbeat: datetime
    status: DeviceStatus
    metadata: Dict[str, Any]

class IoTDeviceMonitor:
    """Main IoT Device Monitoring and Integration Engine"""
    
    def __init__(self):
        self.devices: Dict[str, IoTDevice] = {}
        self.edge_nodes: Dict[str, EdgeNode] = {}
        self.discovery_threads: List[threading.Thread] = []
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=20)
        
        # Network configuration
        self.local_networks = [
            ipaddress.IPv4Network('192.168.1.0/24'),
            ipaddress.IPv4Network('192.168.0.0/24'),
            ipaddress.IPv4Network('10.0.0.0/8'),
            ipaddress.IPv4Network('172.16.0.0/12')
        ]
        
        # Known IoT ports and services
        self.iot_ports = {
            80: 'http_web',
            443: 'https_web',
            554: 'rtsp_camera',
            1883: 'mqtt',
            8883: 'mqtt_tls',
            5683: 'coap',
            8080: 'http_alt',
            9999: 'telnet_iot',
            23: 'telnet',
            502: 'modbus',
            1883: 'mqtt',
            5000: 'upnp',
            1900: 'ssdp_upnp'
        }
        
        # Device fingerprints for identification
        self.device_signatures = {
            'TP-Link': {'ports': [9999], 'banners': ['TP-Link']},
            'Hikvision': {'ports': [554, 8000], 'banners': ['Hikvision']},
            'Nest': {'ports': [443], 'banners': ['Nest']},
            'Ring': {'ports': [443], 'banners': ['Ring']},
            'Philips Hue': {'ports': [80, 443], 'banners': ['Philips']},
            'Sonos': {'ports': [1400], 'banners': ['Sonos']},
            'Samsung SmartThings': {'ports': [39500], 'banners': ['Samsung']},
            'Raspberry Pi': {'ports': [22], 'banners': ['Raspbian', 'raspberry']},
            'Arduino': {'ports': [80], 'banners': ['Arduino']},
            'ESP32': {'ports': [80], 'banners': ['ESP32']},
            'ESP8266': {'ports': [80], 'banners': ['ESP8266']}
        }
        
        # Initialize database connection
        self.setup_database()
        
        # Statistics tracking
        self.stats = {
            'devices_discovered': 0,
            'edge_nodes_discovered': 0,
            'scans_completed': 0,
            'last_scan_duration': 0,
            'total_scan_time': 0,
            'vulnerabilities_found': 0,
            'performance_issues': 0
        }
    
    def setup_database(self):
        """Setup InfluxDB connection for IoT metrics storage"""
        try:
            from collections.ml_analytics.secrets_helper import get_database_url
            db_url = get_database_url('influxdb')
            
            # Parse connection URL
            if '@' in db_url:
                auth_part = db_url.split('//')[1].split('@')[0]
                username, password = auth_part.split(':')
                host_part = db_url.split('@')[1].split(':')[0]
                port = 8086
            else:
                username, password = None, None
                host_part = db_url.split('//')[1].split(':')[0]
                port = 8086
            
            self.influxdb_client = InfluxDBClient(
                host=host_part,
                port=port,
                username=username,
                password=password,
                database='iot_monitoring'
            )
            
            # Create database if it doesn't exist
            try:
                databases = self.influxdb_client.get_list_database()
                if not any(db['name'] == 'iot_monitoring' for db in databases):
                    self.influxdb_client.create_database('iot_monitoring')
                    logger.info("Created iot_monitoring database")
            except Exception as e:
                logger.warning(f"Could not create database: {e}")
            
            logger.info("InfluxDB connection established for IoT monitoring")
            
        except Exception as e:
            logger.error(f"Failed to setup InfluxDB connection: {e}")
            self.influxdb_client = None
    
    async def discover_devices(self):
        """Main device discovery orchestrator"""
        logger.info("Starting IoT device discovery")
        start_time = time.time()
        
        discovery_tasks = []
        
        # Network scanning for all local networks
        for network in self.local_networks:
            task = asyncio.create_task(self.scan_network(network))
            discovery_tasks.append(task)
        
        # UPnP discovery
        discovery_tasks.append(asyncio.create_task(self.upnp_discovery()))
        
        # mDNS/Bonjour discovery
        discovery_tasks.append(asyncio.create_task(self.mdns_discovery()))
        
        # MQTT device discovery
        discovery_tasks.append(asyncio.create_task(self.mqtt_discovery()))
        
        # Wait for all discovery methods to complete
        await asyncio.gather(*discovery_tasks, return_exceptions=True)
        
        # Post-discovery analysis
        await self.analyze_discovered_devices()
        
        duration = time.time() - start_time
        self.stats['scans_completed'] += 1
        self.stats['last_scan_duration'] = duration
        self.stats['total_scan_time'] += duration
        
        logger.info(f"Device discovery completed in {duration:.2f} seconds")
        logger.info(f"Found {len(self.devices)} IoT devices, {len(self.edge_nodes)} edge nodes")
    
    async def scan_network(self, network: ipaddress.IPv4Network):
        """Scan network for IoT devices"""
        logger.info(f"Scanning network: {network}")
        
        # Create tasks for each IP in reasonable chunks
        tasks = []
        for ip in network.hosts():
            if len(tasks) >= 50:  # Process in batches
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
            
            task = asyncio.create_task(self.scan_host(str(ip)))
            tasks.append(task)
        
        # Process remaining tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def scan_host(self, ip: str):
        """Scan individual host for IoT characteristics"""
        try:
            # Skip if we already know this device
            if ip in self.devices:
                return
            
            # Basic connectivity check
            if not await self.is_host_alive(ip):
                return
            
            # Port scan for IoT services
            open_ports = await self.port_scan(ip, list(self.iot_ports.keys()))
            
            if not open_ports:
                return
            
            # Device fingerprinting
            device_info = await self.fingerprint_device(ip, open_ports)
            
            if device_info:
                device = IoTDevice(
                    ip_address=ip,
                    mac_address=device_info.get('mac', 'unknown'),
                    device_type=DeviceType(device_info.get('type', 'unknown')),
                    manufacturer=device_info.get('manufacturer', 'unknown'),
                    model=device_info.get('model', 'unknown'),
                    firmware_version=device_info.get('firmware', 'unknown'),
                    hostname=device_info.get('hostname', f'device-{ip.replace(".", "-")}'),
                    last_seen=datetime.utcnow(),
                    status=DeviceStatus.ONLINE,
                    capabilities=device_info.get('capabilities', []),
                    metadata=device_info.get('metadata', {}),
                    security_info=device_info.get('security', {}),
                    energy_metrics=device_info.get('energy', {}),
                    network_metrics=device_info.get('network', {})
                )
                
                self.devices[ip] = device
                self.stats['devices_discovered'] += 1
                
                # Check if this is also an edge computing node
                if await self.is_edge_node(ip, device_info):
                    await self.register_edge_node(ip, device_info)
                
                logger.info(f"Discovered {device.device_type.value}: {device.hostname} at {ip}")
        
        except Exception as e:
            logger.debug(f"Error scanning {ip}: {e}")
    
    async def is_host_alive(self, ip: str, timeout: float = 1.0) -> bool:
        """Check if host is reachable"""
        try:
            # Try ICMP ping first (requires raw sockets, may fail)
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '1', ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            result = await asyncio.wait_for(proc.wait(), timeout=2.0)
            return result == 0
        except:
            # Fallback to TCP connection attempt
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, 80),
                    timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                return True
            except:
                return False
    
    async def port_scan(self, ip: str, ports: List[int]) -> List[int]:
        """Scan specific ports on host"""
        open_ports = []
        semaphore = asyncio.Semaphore(10)  # Limit concurrent connections
        
        async def check_port(port):
            async with semaphore:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(ip, port),
                        timeout=2.0
                    )
                    writer.close()
                    await writer.wait_closed()
                    return port
                except:
                    return None
        
        tasks = [check_port(port) for port in ports]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, int):
                open_ports.append(result)
        
        return open_ports
    
    async def fingerprint_device(self, ip: str, open_ports: List[int]) -> Optional[Dict[str, Any]]:
        """Attempt to identify device type and characteristics"""
        device_info = {
            'type': 'unknown',
            'manufacturer': 'unknown',
            'model': 'unknown',
            'firmware': 'unknown',
            'hostname': f'device-{ip.replace(".", "-")}',
            'capabilities': [],
            'metadata': {},
            'security': {},
            'energy': {},
            'network': {}
        }
        
        # HTTP banner grabbing
        if 80 in open_ports or 8080 in open_ports:
            http_info = await self.get_http_info(ip, 80 if 80 in open_ports else 8080)
            if http_info:
                device_info.update(http_info)
        
        # HTTPS banner grabbing
        if 443 in open_ports:
            https_info = await self.get_https_info(ip)
            if https_info:
                device_info.update(https_info)
        
        # RTSP for cameras
        if 554 in open_ports:
            device_info['type'] = 'camera'
            device_info['capabilities'].append('video_streaming')
            rtsp_info = await self.get_rtsp_info(ip)
            if rtsp_info:
                device_info.update(rtsp_info)
        
        # MQTT for IoT devices
        if 1883 in open_ports or 8883 in open_ports:
            device_info['capabilities'].append('mqtt_communication')
            mqtt_info = await self.get_mqtt_info(ip)
            if mqtt_info:
                device_info.update(mqtt_info)
        
        # Device signature matching
        for manufacturer, signature in self.device_signatures.items():
            if any(port in open_ports for port in signature['ports']):
                # Additional banner checking would be done here
                device_info['manufacturer'] = manufacturer
                break
        
        # Determine device type based on open ports and capabilities
        device_info['type'] = self.classify_device_type(open_ports, device_info['capabilities'])
        
        # Get MAC address if possible
        mac = await self.get_mac_address(ip)
        if mac:
            device_info['mac'] = mac
        
        return device_info
    
    async def get_http_info(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Get HTTP server information"""
        try:
            async with asyncio.timeout(5):
                url = f"http://{ip}:{port}"
                response = await asyncio.to_thread(requests.get, url, timeout=3)
                
                info = {}
                
                # Server header
                server = response.headers.get('Server', '')
                if server:
                    info['server'] = server
                    
                    # Try to extract manufacturer/model from server string
                    if 'nginx' in server.lower():
                        info['capabilities'] = info.get('capabilities', []) + ['web_server']
                    elif 'apache' in server.lower():
                        info['capabilities'] = info.get('capabilities', []) + ['web_server']
                    elif 'hikvision' in server.lower():
                        info['manufacturer'] = 'Hikvision'
                        info['type'] = 'camera'
                
                # Check for common IoT device indicators
                content = response.text.lower()
                if 'smart home' in content or 'iot' in content:
                    info['type'] = 'smart_switch'
                elif 'camera' in content or 'rtsp' in content:
                    info['type'] = 'camera'
                elif 'thermostat' in content or 'temperature' in content:
                    info['type'] = 'thermostat'
                
                return info
        
        except Exception as e:
            logger.debug(f"HTTP info gathering failed for {ip}:{port}: {e}")
            return None
    
    async def get_https_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get HTTPS certificate and server information"""
        try:
            # Note: Full SSL certificate analysis would be implemented here
            # For now, just attempt basic HTTPS connection
            async with asyncio.timeout(5):
                url = f"https://{ip}"
                response = await asyncio.to_thread(
                    requests.get, url, timeout=3, verify=False
                )
                
                info = {}
                server = response.headers.get('Server', '')
                if server:
                    info['server'] = server
                
                return info
        
        except Exception as e:
            logger.debug(f"HTTPS info gathering failed for {ip}: {e}")
            return None
    
    async def get_rtsp_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get RTSP camera information"""
        try:
            # Basic RTSP OPTIONS request
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 554),
                timeout=3.0
            )
            
            options_request = f"OPTIONS rtsp://{ip}:554/ RTSP/1.0\r\nCSeq: 1\r\n\r\n"
            writer.write(options_request.encode())
            await writer.drain()
            
            response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
            writer.close()
            await writer.wait_closed()
            
            if b'RTSP/1.0 200 OK' in response:
                return {
                    'type': 'camera',
                    'capabilities': ['rtsp_streaming', 'video_recording'],
                    'metadata': {'rtsp_available': True}
                }
        
        except Exception as e:
            logger.debug(f"RTSP info gathering failed for {ip}: {e}")
        
        return None
    
    async def get_mqtt_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get MQTT broker information"""
        try:
            # Basic MQTT connection attempt
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, 1883),
                timeout=3.0
            )
            
            # MQTT CONNECT packet (simplified)
            connect_packet = b'\x10\x0c\x00\x04MQTT\x04\x00\x00\x00\x00\x00'
            writer.write(connect_packet)
            await writer.drain()
            
            response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
            writer.close()
            await writer.wait_closed()
            
            if len(response) > 0:
                return {
                    'capabilities': ['mqtt_broker', 'iot_communication'],
                    'metadata': {'mqtt_available': True}
                }
        
        except Exception as e:
            logger.debug(f"MQTT info gathering failed for {ip}: {e}")
        
        return None
    
    def classify_device_type(self, open_ports: List[int], capabilities: List[str]) -> str:
        """Classify device type based on ports and capabilities"""
        if 554 in open_ports or 'rtsp_streaming' in capabilities:
            return 'camera'
        elif 1883 in open_ports or 8883 in open_ports:
            return 'sensor'  # MQTT usually indicates sensors
        elif 'web_server' in capabilities and 80 in open_ports:
            return 'smart_switch'  # Many smart switches have web interfaces
        elif 502 in open_ports:
            return 'sensor'  # Modbus typically used for industrial sensors
        else:
            return 'unknown'
    
    async def get_mac_address(self, ip: str) -> Optional[str]:
        """Get MAC address for IP (requires ARP table access)"""
        try:
            # Try to get MAC from system ARP table
            proc = await asyncio.create_subprocess_exec(
                'arp', '-n', ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode == 0:
                output = stdout.decode()
                # Parse ARP output to extract MAC address
                import re
                mac_match = re.search(r'([0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2}[:-][0-9a-f]{2})', output, re.IGNORECASE)
                if mac_match:
                    return mac_match.group(1)
        
        except Exception as e:
            logger.debug(f"MAC address lookup failed for {ip}: {e}")
        
        return None
    
    async def upnp_discovery(self):
        """Discover devices using UPnP/SSDP"""
        logger.info("Starting UPnP device discovery")
        
        try:
            # UPnP SSDP discovery
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(5)
            
            # SSDP discovery message
            ssdp_request = (
                'M-SEARCH * HTTP/1.1\r\n'
                'HOST: 239.255.255.250:1900\r\n'
                'MAN: "ssdp:discover"\r\n'
                'ST: upnp:rootdevice\r\n'
                'MX: 3\r\n\r\n'
            )
            
            sock.sendto(ssdp_request.encode(), ('239.255.255.250', 1900))
            
            # Collect responses
            responses = []
            start_time = time.time()
            
            while time.time() - start_time < 5:
                try:
                    data, addr = sock.recvfrom(1024)
                    responses.append((data.decode(), addr))
                except socket.timeout:
                    break
            
            sock.close()
            
            # Process UPnP responses
            for response, addr in responses:
                await self.process_upnp_response(response, addr[0])
        
        except Exception as e:
            logger.error(f"UPnP discovery failed: {e}")
    
    async def process_upnp_response(self, response: str, ip: str):
        """Process UPnP device response"""
        try:
            # Parse UPnP response headers
            headers = {}
            for line in response.split('\r\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Extract device information
            device_info = {
                'type': 'smart_switch',  # Most UPnP devices are smart home devices
                'capabilities': ['upnp_discovery'],
                'metadata': {
                    'upnp_location': headers.get('location', ''),
                    'upnp_server': headers.get('server', ''),
                    'upnp_st': headers.get('st', '')
                }
            }
            
            # Try to get more detailed device description
            if 'location' in headers:
                detailed_info = await self.get_upnp_device_description(headers['location'])
                if detailed_info:
                    device_info.update(detailed_info)
            
            # Create or update device entry
            if ip not in self.devices:
                device = IoTDevice(
                    ip_address=ip,
                    mac_address=await self.get_mac_address(ip) or 'unknown',
                    device_type=DeviceType(device_info.get('type', 'unknown')),
                    manufacturer=device_info.get('manufacturer', 'unknown'),
                    model=device_info.get('model', 'unknown'),
                    firmware_version=device_info.get('firmware', 'unknown'),
                    hostname=device_info.get('hostname', f'upnp-{ip.replace(".", "-")}'),
                    last_seen=datetime.utcnow(),
                    status=DeviceStatus.ONLINE,
                    capabilities=device_info.get('capabilities', []),
                    metadata=device_info.get('metadata', {}),
                    security_info={},
                    energy_metrics={},
                    network_metrics={}
                )
                
                self.devices[ip] = device
                self.stats['devices_discovered'] += 1
                logger.info(f"UPnP discovered: {device.hostname} at {ip}")
        
        except Exception as e:
            logger.debug(f"Failed to process UPnP response from {ip}: {e}")
    
    async def get_upnp_device_description(self, location_url: str) -> Optional[Dict[str, Any]]:
        """Get detailed UPnP device description"""
        try:
            response = await asyncio.to_thread(requests.get, location_url, timeout=5)
            
            # Parse XML response (simplified - would use proper XML parser)
            content = response.text
            info = {}
            
            # Extract basic device information
            if '<friendlyName>' in content:
                start = content.find('<friendlyName>') + len('<friendlyName>')
                end = content.find('</friendlyName>')
                info['hostname'] = content[start:end]
            
            if '<manufacturer>' in content:
                start = content.find('<manufacturer>') + len('<manufacturer>')
                end = content.find('</manufacturer>')
                info['manufacturer'] = content[start:end]
            
            if '<modelName>' in content:
                start = content.find('<modelName>') + len('<modelName>')
                end = content.find('</modelName>')
                info['model'] = content[start:end]
            
            return info
        
        except Exception as e:
            logger.debug(f"Failed to get UPnP device description from {location_url}: {e}")
            return None
    
    async def mdns_discovery(self):
        """Discover devices using mDNS/Bonjour"""
        logger.info("Starting mDNS device discovery")
        
        try:
            # Query common mDNS service types
            service_types = [
                '_http._tcp.local',
                '_https._tcp.local',
                '_ipp._tcp.local',
                '_airplay._tcp.local',
                '_googlecast._tcp.local',
                '_hap._tcp.local',  # HomeKit
                '_mqtt._tcp.local'
            ]
            
            # Use system tools for mDNS discovery
            for service_type in service_types:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        'avahi-browse', '-r', '-t', service_type,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    
                    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
                    
                    if proc.returncode == 0:
                        await self.process_mdns_results(stdout.decode(), service_type)
                
                except (FileNotFoundError, asyncio.TimeoutError):
                    # avahi-browse not available or timeout
                    logger.debug(f"mDNS discovery for {service_type} failed or timed out")
                    continue
        
        except Exception as e:
            logger.error(f"mDNS discovery failed: {e}")
    
    async def process_mdns_results(self, output: str, service_type: str):
        """Process mDNS discovery results"""
        # Parse mDNS output and extract device information
        # Implementation would parse avahi-browse output format
        logger.debug(f"Processing mDNS results for {service_type}")
        # This would be expanded to properly parse mDNS responses
    
    async def mqtt_discovery(self):
        """Discover MQTT-based IoT devices"""
        logger.info("Starting MQTT device discovery")
        
        # Try to connect to common MQTT brokers on the network
        mqtt_ports = [1883, 8883]
        
        for network in self.local_networks:
            for ip in list(network.hosts())[:10]:  # Sample first 10 IPs
                for port in mqtt_ports:
                    try:
                        # Basic MQTT broker detection
                        reader, writer = await asyncio.wait_for(
                            asyncio.open_connection(str(ip), port),
                            timeout=2.0
                        )
                        
                        writer.close()
                        await writer.wait_closed()
                        
                        # If connection successful, mark as potential MQTT broker
                        logger.info(f"Potential MQTT broker found at {ip}:{port}")
                        
                        # Would implement actual MQTT discovery here
                        
                    except:
                        continue
    
    async def analyze_discovered_devices(self):
        """Analyze discovered devices for security and performance insights"""
        logger.info("Analyzing discovered devices")
        
        vulnerability_count = 0
        performance_issues = 0
        
        for ip, device in self.devices.items():
            # Security analysis
            security_issues = await self.analyze_device_security(device)
            device.security_info.update(security_issues)
            vulnerability_count += len(security_issues.get('vulnerabilities', []))
            
            # Performance analysis
            perf_metrics = await self.analyze_device_performance(device)
            device.network_metrics.update(perf_metrics)
            if perf_metrics.get('response_time', 0) > 5000:  # 5 second threshold
                performance_issues += 1
        
        self.stats['vulnerabilities_found'] = vulnerability_count
        self.stats['performance_issues'] = performance_issues
        
        logger.info(f"Analysis complete: {vulnerability_count} vulnerabilities, {performance_issues} performance issues")
    
    async def analyze_device_security(self, device: IoTDevice) -> Dict[str, Any]:
        """Analyze device for security vulnerabilities"""
        security_info = {
            'vulnerabilities': [],
            'security_score': 100,
            'recommendations': []
        }
        
        try:
            # Check for default credentials
            if await self.check_default_credentials(device.ip_address):
                security_info['vulnerabilities'].append('default_credentials')
                security_info['security_score'] -= 30
                security_info['recommendations'].append('Change default credentials')
            
            # Check for unencrypted communications
            if 'mqtt_communication' in device.capabilities and 1883 in await self.port_scan(device.ip_address, [1883]):
                security_info['vulnerabilities'].append('unencrypted_mqtt')
                security_info['security_score'] -= 20
                security_info['recommendations'].append('Enable MQTT TLS encryption')
            
            # Check for weak protocols
            if await self.check_weak_protocols(device.ip_address):
                security_info['vulnerabilities'].append('weak_protocols')
                security_info['security_score'] -= 15
                security_info['recommendations'].append('Disable weak protocols (Telnet, HTTP)')
            
        except Exception as e:
            logger.debug(f"Security analysis failed for {device.ip_address}: {e}")
        
        return security_info
    
    async def check_default_credentials(self, ip: str) -> bool:
        """Check for default credentials on common services"""
        default_creds = [
            ('admin', 'admin'),
            ('admin', ''),
            ('admin', 'password'),
            ('root', 'root'),
            ('admin', '12345')
        ]
        
        # Check HTTP basic auth
        try:
            for username, password in default_creds:
                url = f"http://{ip}"
                response = await asyncio.to_thread(
                    requests.get, url, auth=(username, password), timeout=3
                )
                if response.status_code == 200:
                    return True
        except:
            pass
        
        return False
    
    async def check_weak_protocols(self, ip: str) -> bool:
        """Check for weak/insecure protocols"""
        weak_ports = [23, 21, 80]  # Telnet, FTP, HTTP
        open_weak_ports = await self.port_scan(ip, weak_ports)
        return len(open_weak_ports) > 0
    
    async def analyze_device_performance(self, device: IoTDevice) -> Dict[str, float]:
        """Analyze device network performance"""
        metrics = {}
        
        try:
            # Measure response time
            start_time = time.time()
            alive = await self.is_host_alive(device.ip_address, timeout=5.0)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            metrics['response_time'] = response_time
            metrics['availability'] = 1.0 if alive else 0.0
            
            # Estimate bandwidth usage (simplified)
            metrics['estimated_bandwidth'] = 1.0  # Would implement actual bandwidth measurement
            
        except Exception as e:
            logger.debug(f"Performance analysis failed for {device.ip_address}: {e}")
            metrics['response_time'] = 999999  # High value to indicate failure
            metrics['availability'] = 0.0
        
        return metrics
    
    async def is_edge_node(self, ip: str, device_info: Dict[str, Any]) -> bool:
        """Determine if device is an edge computing node"""
        # Look for indicators of edge computing capability
        edge_indicators = [
            'raspberry' in device_info.get('hostname', '').lower(),
            'pi' in device_info.get('hostname', '').lower(),
            'edge' in device_info.get('hostname', '').lower(),
            'compute' in device_info.get('hostname', '').lower(),
            device_info.get('manufacturer', '').lower() in ['raspberry', 'nvidia', 'intel']
        ]
        
        return any(edge_indicators)
    
    async def register_edge_node(self, ip: str, device_info: Dict[str, Any]):
        """Register device as edge computing node"""
        node = EdgeNode(
            node_id=f"edge-{ip.replace('.', '-')}",
            ip_address=ip,
            hostname=device_info.get('hostname', f'edge-{ip}'),
            cpu_cores=4,  # Default values - would be detected
            memory_gb=2.0,
            storage_gb=32.0,
            gpu_available=False,
            compute_capacity=1.0,
            current_load=0.0,
            services_running=[],
            last_heartbeat=datetime.utcnow(),
            status=DeviceStatus.ONLINE,
            metadata=device_info.get('metadata', {})
        )
        
        self.edge_nodes[ip] = node
        self.stats['edge_nodes_discovered'] += 1
        logger.info(f"Registered edge node: {node.hostname} at {ip}")
    
    async def monitor_device_metrics(self):
        """Continuously monitor device metrics"""
        while self.running:
            try:
                for ip, device in self.devices.items():
                    # Update device status
                    device.status = DeviceStatus.ONLINE if await self.is_host_alive(ip) else DeviceStatus.OFFLINE
                    device.last_seen = datetime.utcnow()
                    
                    # Collect metrics
                    metrics = await self.collect_device_metrics(device)
                    if metrics:
                        await self.store_device_metrics(device, metrics)
                
                # Monitor edge nodes
                for ip, node in self.edge_nodes.items():
                    node_metrics = await self.collect_edge_metrics(node)
                    if node_metrics:
                        await self.store_edge_metrics(node, node_metrics)
                
                # Send periodic updates
                await self.send_monitoring_update()
                
                # Wait before next monitoring cycle
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                await asyncio.sleep(60)
    
    async def collect_device_metrics(self, device: IoTDevice) -> Optional[Dict[str, Any]]:
        """Collect metrics from IoT device"""
        try:
            metrics = {
                'timestamp': datetime.utcnow(),
                'device_ip': device.ip_address,
                'status': device.status.value,
                'response_time': 0,
                'packet_loss': 0,
                'signal_strength': -50,  # dBm (estimated)
                'power_consumption': 5.0,  # Watts (estimated)
                'data_throughput': 1000  # bytes/sec (estimated)
            }
            
            # Measure actual response time
            start_time = time.time()
            alive = await self.is_host_alive(device.ip_address)
            metrics['response_time'] = (time.time() - start_time) * 1000
            
            if not alive:
                metrics['packet_loss'] = 100
            
            return metrics
            
        except Exception as e:
            logger.debug(f"Failed to collect metrics for {device.ip_address}: {e}")
            return None
    
    async def collect_edge_metrics(self, node: EdgeNode) -> Optional[Dict[str, Any]]:
        """Collect metrics from edge computing node"""
        try:
            metrics = {
                'timestamp': datetime.utcnow(),
                'node_id': node.node_id,
                'ip_address': node.ip_address,
                'cpu_usage': 25.0,  # Would get actual CPU usage
                'memory_usage': 60.0,  # Percentage
                'storage_usage': 45.0,  # Percentage
                'network_io': 1000,  # bytes/sec
                'active_services': len(node.services_running),
                'compute_load': node.current_load
            }
            
            return metrics
            
        except Exception as e:
            logger.debug(f"Failed to collect edge metrics for {node.node_id}: {e}")
            return None
    
    async def store_device_metrics(self, device: IoTDevice, metrics: Dict[str, Any]):
        """Store device metrics in InfluxDB"""
        if not self.influxdb_client:
            return
        
        try:
            points = [{
                'measurement': 'iot_device_metrics',
                'tags': {
                    'device_ip': device.ip_address,
                    'device_type': device.device_type.value,
                    'manufacturer': device.manufacturer,
                    'hostname': device.hostname
                },
                'fields': {
                    'response_time': metrics['response_time'],
                    'packet_loss': metrics['packet_loss'],
                    'signal_strength': metrics['signal_strength'],
                    'power_consumption': metrics['power_consumption'],
                    'data_throughput': metrics['data_throughput'],
                    'status_online': 1 if metrics['status'] == 'online' else 0
                },
                'time': metrics['timestamp']
            }]
            
            self.influxdb_client.write_points(points)
            
        except Exception as e:
            logger.error(f"Failed to store device metrics: {e}")
    
    async def store_edge_metrics(self, node: EdgeNode, metrics: Dict[str, Any]):
        """Store edge node metrics in InfluxDB"""
        if not self.influxdb_client:
            return
        
        try:
            points = [{
                'measurement': 'edge_node_metrics',
                'tags': {
                    'node_id': node.node_id,
                    'hostname': node.hostname,
                    'ip_address': node.ip_address
                },
                'fields': {
                    'cpu_usage': metrics['cpu_usage'],
                    'memory_usage': metrics['memory_usage'],
                    'storage_usage': metrics['storage_usage'],
                    'network_io': metrics['network_io'],
                    'active_services': metrics['active_services'],
                    'compute_load': metrics['compute_load']
                },
                'time': metrics['timestamp']
            }]
            
            self.influxdb_client.write_points(points)
            
        except Exception as e:
            logger.error(f"Failed to store edge metrics: {e}")
    
    async def send_monitoring_update(self):
        """Send periodic monitoring updates"""
        try:
            from collections.ml_analytics.secrets_helper import get_slack_webhook
            webhook_url = get_slack_webhook()
            
            if webhook_url:
                # Create summary message
                online_devices = sum(1 for d in self.devices.values() if d.status == DeviceStatus.ONLINE)
                total_devices = len(self.devices)
                total_edge_nodes = len(self.edge_nodes)
                
                message = {
                    'text': f'🏠 IoT Monitoring Update',
                    'attachments': [
                        {
                            'color': 'good' if online_devices == total_devices else 'warning',
                            'fields': [
                                {'title': 'Devices Online', 'value': f'{online_devices}/{total_devices}', 'short': True},
                                {'title': 'Edge Nodes', 'value': str(total_edge_nodes), 'short': True},
                                {'title': 'Vulnerabilities', 'value': str(self.stats['vulnerabilities_found']), 'short': True},
                                {'title': 'Performance Issues', 'value': str(self.stats['performance_issues']), 'short': True}
                            ]
                        }
                    ]
                }
                
                await asyncio.to_thread(requests.post, webhook_url, json=message, timeout=5)
                
        except Exception as e:
            logger.error(f"Failed to send monitoring update: {e}")
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get current monitoring statistics"""
        return {
            'total_devices': len(self.devices),
            'online_devices': sum(1 for d in self.devices.values() if d.status == DeviceStatus.ONLINE),
            'total_edge_nodes': len(self.edge_nodes),
            'device_types': {
                device_type.value: sum(1 for d in self.devices.values() if d.device_type == device_type)
                for device_type in DeviceType
            },
            'manufacturers': {
                manufacturer: sum(1 for d in self.devices.values() if d.manufacturer == manufacturer)
                for manufacturer in set(d.manufacturer for d in self.devices.values())
            },
            'statistics': self.stats
        }
    
    async def start_monitoring(self):
        """Start the IoT monitoring system"""
        logger.info("Starting IoT Device Monitor")
        self.running = True
        
        # Start monitoring tasks
        tasks = [
            asyncio.create_task(self.discover_devices()),
            asyncio.create_task(self.monitor_device_metrics())
        ]
        
        # Run initial discovery
        await self.discover_devices()
        
        # Start continuous monitoring
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_monitoring(self):
        """Stop the monitoring system"""
        logger.info("Stopping IoT Device Monitor")
        self.running = False

def main():
    """Main entry point for IoT Device Monitor"""
    monitor = IoTDeviceMonitor()
    
    try:
        asyncio.run(monitor.start_monitoring())
    except KeyboardInterrupt:
        logger.info("IoT monitoring stopped by user")
    except Exception as e:
        logger.error(f"IoT monitoring error: {e}")

if __name__ == "__main__":
    main()
