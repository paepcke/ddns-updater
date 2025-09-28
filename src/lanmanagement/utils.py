# **********************************************************
#
# @Author: Andreas Paepcke
# @Date:   2025-09-14 20:11:22
# @File:   /Users/paepcke/VSCodeWorkspaces/lan-gateway/src/gateway_controls/utils.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-27 17:06:35
#
# **********************************************************

# Utilities for LAN gateway management

import ipaddress
import re
import socket
import uuid
import platform

class Utils:

    #------------------------------------
    # resolve_hostname_to_ip
    #-------------------

    @staticmethod
    def resolve_hostname_to_ip(hostname):
        """
        Resolve hostname to IP address
        """
        try:
            return socket.gethostbyname(hostname)
        except Exception:
            return None

    #------------------------------------
    # is_valid_mac
    #-------------------

    @staticmethod
    def is_valid_mac(mac):
        """
        Check if string is a valid MAC address
        """
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        return bool(mac_pattern.match(mac))

    #------------------------------------
    # is_valid_ip
    #-------------------

    @staticmethod
    def is_valid_ip(ip):
        """
        Check if string is a valid IP address
        """
        try:
            # Tries to create an IPv4 or IPv6 address object
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    #------------------------------------
    # normalize_mac
    #-------------------
    
    @staticmethod
    def normalize_mac(mac):
        """
        Normalize MAC address format to XX:XX:XX:XX:XX:XX

        :raises ValueError if wrong number of octets.
        """
        # Remove any separators and convert to uppercase
        mac = re.sub(r'[:-]', '', mac).upper()
        
        # Add colons
        if len(mac) == 12:
            return ':'.join([mac[i:i+2] for i in range(0, 12, 2)])
        raise ValueError(f"MAC address {mac} has wrong number of octets (should be 12)")

    #------------------------------------
    # get_own_os
    #-------------------

    @staticmethod
    def get_own_os(simple=True):
        '''
        Returns this machine's operating system,
        including 

        :return: _description_
        :rtype: _type_
        '''
        os_name = platform.system().lower()
        os_version = platform.release()
        if os_name == 'darwin':
            # We can get more info:
            darwin_version = os_version
            macos_version  = platform.mac_ver()[0]
            machine        = platform.machine()
            os_name = 'macos'
            if simple:
                os_info = f"{os_name}{macos_version}"
            else:
                # Get full info:
                os_info = f"{os_name}{macos_version}_darwin{darwin_version}_{machine}"
        elif os_name == 'linux':
            # platform.freedesktop_os_release() returns:
            #    {'NAME': 'Ubuntu', 
            #     'ID': 'ubuntu', 
            #     'PRETTY_NAME': 'Ubuntu 24.04.2 LTS', 
            #     'VERSION_ID': '24.04', 
            #     'VERSION': '24.04.2 LTS (Noble Numbat)', 
            #     'VERSION_CODENAME': 'noble', 
            #     'ID_LIKE': 'debian', 
            #     'HOME_URL': 'https://www.ubuntu.com/', 
            #     'SUPPORT_URL': 'https://help.ubuntu.com/', 
            #     'BUG_REPORT_URL': 'https://bugs.launchpad.net/ubuntu/', 
            #     'PRIVACY_POLICY_URL': 'https://www.ubuntu.com/legal/terms-and-policies/privacy-policy', 
            #     'UBUNTU_CODENAME': 'noble', 
            #     'LOGO': 'ubuntu-logo'}
            linux_raw_info = platform.freedesktop_os_release()
            # Get 'ubuntu' or whatever else:
            maker_name  = linux_raw_info.get('ID', 'flavorUnknown')
            # Get 24.04, or such
            version_num = linux_raw_info.get('VERSION_ID', 'versionUnknown')
            kernel_version = platform.release()
            machine = platform.machine()

            if simple:
                # Leave out anything we don't know:
                os_info = "linux"
                if maker_name != 'flavorUnknown':
                    os_info += f"_{maker_name}"
                if version_num != 'versionUnknown':
                    os_info += f"_{version_num}"
            else:
                # Simple is False, get the full Monte:
                # Get the long 'pretty name':
                if (pretty_name := linux_raw_info.get('PRETTY_NAME', None)) is None:
                    # Pretty name unavailable: coble something less together:
                    pretty_name = f"linux_{maker_name}_{version_num}"
                else:
                    # Got pretty name, replace spaces with underscores:
                    pretty_name = pretty_name.replace(' ', '_')

                os_info = f"{os_name}_{pretty_name}_kernel{kernel_version}_{machine}"
        else:
            # Windows or other:
            os_info = os_name

        return os_info

    #------------------------------------
    # get_own_mac
    #-------------------

    @staticmethod
    def get_own_mac():
        '''
        Return this machine's own MAC address

        :return: this machine's active MAC address
        :rtype: str
        '''
        mac = uuid.getnode()
        # Convert integer to hex string and format as MAC
        mac_hex = format(mac, '012x')  # 12 hex digits (48 bits)
        mac_address = ':'.join([mac_hex[i:i+2] for i in range(0, 12, 2)])        
        return mac_address

    #------------------------------------
    # get_own_ip
    #-------------------

    @staticmethod
    def get_own_ip():
        '''
        Return your own IP address on the active NIC

        :return: own machine's IP address
        :rtype: str
        '''
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip =  s.getsockname()[0]        
        return ip

    #------------------------------------
    # get_own_hostname
    #-------------------

    @staticmethod
    def get_own_hostname(short_format=False):
        '''
        Returns own machine's hostname with full domain,
        like: 'sparky.attlocal.net' or 'quintus.stanford.edu'

        :param short_format: whether to just return the name
            without the domain.
        :type short_format: bool
        :return: _description_
        :rtype: _type_
        '''
        hostname = socket.gethostname()
        if short_format:
            hostname = hostname.split('.')[0]
        return hostname
    
    #------------------------------------
    # get_hostname_from_ip
    #-------------------    

    @staticmethod
    def get_hostname_from_ip(ip_address):
        '''
        Given an IP, return the respective hostname

        :param ip_address: _description_
        :type ip_address: _type_
        :return: _description_
        :rtype: _type_
        '''
        try:
            hostname = socket.gethostbyaddr(ip_address)
            return hostname[0] # Returns the first hostname found
        except socket.error as e:
            raise RuntimeError(f'{e}')

	#------------------------------------
	# check_domain_syntax
	#-------------------

    @staticmethod
    def check_domain_syntax(domain_string):
        """
        Checks if a string is a validly formatted Internet domain name.

        The validation is based on RFCs 1034, 1123, and 952.
        It checks for the overall structure of a domain name, including:
        - Overall length limit (up to 253 characters).
        - Label length limit (1 to 63 characters).
        - Labels can contain letters (a-z, A-Z), digits (0-9), and hyphens (-).
        - Labels must not start or end with a hyphen.
        - Top-level domain (TLD) must be at least 2 characters long.

        :param domain_string: the domain name to be checked
        :type domain_string: str
        :returns: whether or not string is syntactically a legal domain
        :rtype: bool
        """

        if not isinstance(domain_string, str) or not domain_string:
            return False

        # A regular expression pattern for a domain name.
        # The pattern is broken down into parts for clarity:
        # ^                            - Anchor to the start of the string.
        # (?!-)                        - Negative lookahead to ensure the first character is not a hyphen.
        # (?:[a-zA-Z0-9-]{1,63})      - Match a label (1-63 chars: letters, digits, hyphens).
        # (?<!-)                       - Negative lookbehind to ensure the label does not end with a hyphen.
        # (?:\.[a-zA-Z0-9-]{1,63})* - Match zero or more subdomains, each starting with a dot.
        # (?<!-)(?:\.[a-zA-Z]{2,})    - Match the TLD, which must not end with a hyphen and must be at least 2 chars.
        # $                            - Anchor to the end of the string.
        # The domain name as a whole must be at most 253 characters.

        domain_regex = re.compile(
            r'^(?!-)(?:[a-zA-Z0-9-]{1,63})(?<!-)(?:\.[a-zA-Z0-9-]{1,63})*(?<!-)(?:\.[a-zA-Z]{2,})$'
        )

        # Check overall length first to be more efficient.
        if len(domain_string) > 253:
            return False

        return bool(domain_regex.match(domain_string))		


