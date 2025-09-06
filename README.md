# Piolink-PLOS-Autotest

A comprehensive automated testing framework for Piolink PLOS (Piolink Operating System) network switches. This project provides automated testing capabilities for various network switch functionalities including port management, VLAN configuration, STP, LACP, and many other networking protocols.

## Overview

The Piolink-PLOS-Autotest is a Python-based testing framework designed to automate the testing of network switch functionalities. It supports multiple test types and can manage multiple devices simultaneously through telnet connections. The framework generates detailed test reports in Excel format and maintains comprehensive logging for test analysis.

## Features

### Core Functionality
- **Multi-device Management**: Supports testing of multiple network switches simultaneously
- **Telnet-based Communication**: Uses telnet connections for device management and command execution
- **Comprehensive Test Suite**: Includes 29 different test types covering various networking protocols
- **Automated Report Generation**: Generates detailed Excel reports with test results and statistics
- **Logging and Backup**: Maintains comprehensive logs and backup systems for test data
- **Threading Support**: Utilizes multi-threading for parallel test execution

### Supported Test Types

1. **Port Management Tests**
   - Port Mapping Test
   - Port Shutdown Test
   - Port Speed Test
   - Port Duplex Test
   - Port MDIX Test
   - Port Flow Control Test
   - Port Storm Control Test
   - Port EEE (Energy Efficient Ethernet) Test
   - Port Jumbo Frame Test
   - Port Cable Diagnostics Test
   - Port Mirroring Test

2. **Protocol Tests**
   - LLDP (Link Layer Discovery Protocol) Test
   - UDLD (Unidirectional Link Detection) Test
   - LACP (Link Aggregation Control Protocol) Test
   - STP (Spanning Tree Protocol) Test
   - STP & LACP Combined Test

3. **VLAN Tests**
   - Switch Mode (VLAN) Test
   - Private VLAN Test
   - Voice VLAN Test

4. **Routing and Network Tests**
   - Ping Test
   - Static Route Test
   - IGMP Snooping Test
   - L2 Smoke Test

5. **MAC Address Management Tests**
   - MAC Table Test
   - MAC Address Limit Test
   - Static MAC Address Test
   - MAC Ageing Time Test
   - ARP Test

## Project Structure

```
Piolink-PLOS-Autotest/
├── main.py                          # Main entry point
├── requirements.txt                 # Python dependencies
├── Makefile                        # Build and setup automation
├── autotest/                       # Core testing framework
│   ├── Host.py                     # Host connection management
│   ├── Run_test.py                 # Test execution engine
│   ├── Tools.py                    # Utility functions
│   ├── Log.py                      # Logging and backup system
│   ├── Print.py                    # Display utilities
│   ├── Parsing.py                  # Test result parsing
│   └── resources/                  # Configuration and scripts
│       ├── Data.py                 # Data management
│       ├── env_config.yaml         # Environment configuration
│       ├── config/                 # Device configurations
│       ├── script/                 # Test scripts
│       └── images/                 # Report images
├── tests/                          # Test modules
├── backup/                         # Test logs and reports
└── README.md                       # This file
```

## Installation

### Prerequisites
- Python 3.7 or higher
- Network access to target switches
- Telnet connectivity to devices

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Piolink-PLOS-Autotest
   ```

2. **Create virtual environment**
   ```bash
   make install
   ```
   or manually:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure devices**
   - Place device configuration files in `autotest/resources/config/`
   - Configure device profiles in `autotest/resources/config/profile/`
   - Update `autotest/resources/env_config.yaml` for test settings

## Usage

### Basic Commands

```bash
# Display help
./main.py

# List available test types
./main.py list

# Select specific test types (e.g., tests 0-5, 8, 20-24)
./main.py list 0-5,8,20-24

# Select all test types
./main.py list all

# Display device configuration
./main.py config

# Initialize devices (with optional reboot)
./main.py init
./main.py init reboot

# Update PLOS image
./main.py update

# Run tests (with optional reboot)
./main.py run
./main.py run reboot
```

### Configuration

#### Device Configuration
Create device configuration files in `autotest/resources/config/` with the following format:
```
dev_name: HOST1
dev_con_ip: 192.168.1.100
dev_console: 23
dev_prompt: HOST1
dev_type: PLOS-SWITCH
#id: admin
#passwd: password
dev_host: y
osname: plos-1.0.0
osupdate: y
uplink_port: ge1
input_port: ge2
output_port: ge3
dev_port1: ge4
dev_port2: ge5
dev_port3: ge6
dev_port4: ge7
nbr_port1: ge8
nbr_port2: ge9
nbr_port3: ge10
nbr_port4: ge11
1g_max_port: 8
2_5g_max_port: 0
5g_max_port: 0
10g_max_port: 0
1g_phy: BCM
2_5g_phy: default
5g_phy: default
10g_phy: default
sdk_type: BCM
board_type: BCM56960
not_support: Private-Vlan,STP&LACP
```

#### Test Configuration
Modify `autotest/resources/env_config.yaml` to enable/disable specific test types and configure test parameters.

## Test Execution Flow

1. **Initialization**: Devices are initialized with basic configuration
2. **Connection Setup**: Telnet connections are established to all devices
3. **Test Execution**: Selected tests are executed in sequence
4. **Data Collection**: Test results are collected and parsed
5. **Report Generation**: Excel reports are generated with detailed results
6. **Logging**: All activities are logged for analysis

## Output and Reports

### Test Reports
- **Excel Format**: Detailed test results in `.xlsx` format
- **Summary Sheet**: Overview of all test results with pass/fail counts
- **Individual Test Sheets**: Detailed results for each test type
- **Visual Elements**: Network diagrams and charts included in reports

### Logging
- **Test Logs**: Detailed command execution logs
- **Statistics Logs**: Test result summaries
- **Current Logs**: Real-time execution logs
- **Backup System**: Automatic backup of all test data

## Supported Devices

The framework supports various Piolink PLOS-based network switches with different configurations:
- Different port types (1G, 2.5G, 5G, 10G)
- Various PHY types (BCM, RTL, SERDES)
- Different SDK types (BCM, RTK)
- Multiple board types

## Dependencies

- **PyYAML**: Configuration file parsing
- **pandas**: Data manipulation and Excel report generation
- **XlsxWriter**: Excel file creation
- **dataclasses**: Data structure management (Python < 3.7)

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Verify network connectivity to devices
   - Check telnet port availability
   - Verify device credentials

2. **Test Failures**
   - Check device configuration
   - Verify test script syntax
   - Review device compatibility

3. **Report Generation Issues**
   - Ensure backup directory permissions
   - Check available disk space
   - Verify Excel file access

### Log Analysis
- Check `backup/current_log/` for real-time execution logs
- Review `backup/test-logs/` for detailed test execution logs
- Examine `backup/stat-logs/` for test result summaries

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is proprietary software developed by Piolink. Please contact Piolink for licensing information.

## Support

For technical support and questions, please contact the Piolink development team or refer to the internal documentation.

## Version History

- **v1.0**: Initial release with basic testing framework
- **Current**: Enhanced with comprehensive test suite and reporting capabilities

---

*This README provides an overview of the Piolink-PLOS-Autotest framework. For detailed implementation information, refer to the source code and internal documentation.*