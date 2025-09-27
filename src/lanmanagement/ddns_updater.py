#!/usr/bin/env python3
# **********************************************************
#
# @Author: Daniel Paepcke
# @Date:   2025-09-19 15:03:46
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/ddns_updater.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-27 15:50:23
# @ modified by Andreas Paepcke
#
# **********************************************************

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import subprocess, sys

import requests
from requests.exceptions import RequestException, \
								ConnectionError, \
								Timeout, \
								HTTPError


src_dir = str(Path(__file__).parent.parent.resolve())
if src_dir not in sys.path:
	sys.path.insert(0, src_dir)
from lanmanagement.ddns_service_adapters import DDNSServiceManager

class DDNSUpdater:

	# Pwd to DDNS server: $HOME/.ssh/ddns_password:
	DDNS_PASSWORD_FILE = str(Path(os.getenv('HOME')) / '.ssh/ddns_password')

	# Logs rotating among five files in current-dir/logs:	
	DDNS_LOG_FILE      = str(Path(__file__).parent / 'logs/ddns.log')
	MAX_LOGFILE_SIZE   = 100 * 1024  # 100 KB
	# Number of log files to keep; rotation among them:
	BACKUP_COUNT 	   = 5
	
    # Server from which to learn one's own IP:
	WHATS_MY_IP_URL = 'https://4.laxa.org'

	#------------------------------------
	# Constructor
	#-------------------	

	def __init__(self, service_nm: str, config_file: str, debug: bool=False):
		'''
		Prepare for IP check-and-update workflow. Service name is
		the DDNS service company, such as 'namecheap'. The config_file
		is a .ini file with (at least) an information section on the
		service to use. That section contains host, domain, and other
		info. See file ddns_service_adapters.py for details.

		:param service_nm: name of DDNS service to use
		:type host: str
		:param config_file: path to config file
		:type domain: str
		'''
		self.service_nm = service_nm
		self.debug = debug

		self.logger = self.setup_logging(
			DDNSUpdater.DDNS_LOG_FILE,
			DDNSUpdater.MAX_LOGFILE_SIZE,
			DDNSUpdater.BACKUP_COUNT)

		# The OS level 'dig' program: obtains host infos
		self.dig_binary = shutil.which('dig')
		if self.dig_binary is None:
			self.logger.error("Could not find needed command 'dig'")
			sys.exit(1)

		# Obtain a DDNS service adapter that will provide
		# update URLs appropriate for the chosen service provider:
		ddns_srv_manager = DDNSServiceManager(config_file)
		self.service_adapter = ddns_srv_manager.get_service_adapter(service_nm)
		
    	# Get config Section structure, which acts like:
		#      {"host": "myhost",
		#       "domain": "mydomain", 
		#            ...
		#       }
		self.options: dict[str,str] = self.service_adapter.service_options()
		try:
			self.host = self.options['host']
		except KeyError:
			self.logger.error(f"Init file at {config_file} has no entry for 'host'")
			sys.exit(1)
		try:
			self.domain = self.options['domain']
		except KeyError:
			self.logger.error(f"Init file at {config_file} has no entry for 'domain'")
			sys.exit(1)

		self.report_own_ip()		

	#------------------------------------
	# report_own_ip
	#-------------------

	def report_own_ip(self):
		'''
		Obtains this host's current IP, and compares it with 
		the DDNS service's IP for this host. If the two IPs
		differ, the DDNS service is updated to be the current
		IP.

		Logs the activity.
		'''

		cur_own_ip = self.cur_own_ip()
		cur_registered_ip = self.current_registered_ip()
		if cur_own_ip == cur_registered_ip:
			# Nothing to report
			return
		
		self.logger.info(f"IP changed from {cur_registered_ip} to {cur_own_ip}")

		update_url = self.service_adapter.ddns_update_url(cur_own_ip)
		if self.debug:
			# Bypass the actual updating, which would required sudo
			self.logger.info("Bypassing DDNS service update because --debug")
			return

		try:
			_response = self.fetch_flex(update_url, user_agent='curl')
		except Exception as e:
			msg = (f"DDNS update script failed to obtain new A record "
					f"via URL {update_url}: {e}")
			self.logger.error(msg)
			return
		else:
			# Log the success:
			msg = f"Reported updated {cur_registered_ip} => {cur_own_ip}"
			self.logger.info(msg)

	#------------------------------------
	# services_list
	#-------------------

	def services_list(self) -> list[str]:
		'''
		Return a list of currently implemented DDNS services

		:return: list of all implemented DDNS services
		:rtype: list[str]
		'''

		# A classmethod on DDNSServiceManager provides
		# the list

		service_names = self.service_adapter.services_list()
		return service_names

	#------------------------------------
	# get_dns_server
	#-------------------	

	def get_dns_server(self, domain: str) -> str:
		'''
		Given the domain for which IP is to be updated
		return one of the domain's DNS servers. Result
		example: 
		   'dns1.namecheaphosting.com.'

		:return: host name of DNS server for host/domain of interest
		:rtype: str
		:raises RuntimeError if OS level 'dig' command fails
		'''
		dig_ns_cmd = [self.dig_binary, 'ns', domain, '+short']
		# A successful dig command prints two DNS servers to
		# stdout, like:
		#    dns1.namecheaphosting.com.
		#    dns2.namecheaphosting.com.		

		dig_proc = subprocess.run(dig_ns_cmd, capture_output=True, text=True)
		if dig_proc.returncode != 0:
			msg = f"DDNS update script failed to identify authoritative NS: {dig_proc.stderr}"
			raise RuntimeError(msg)
		
		authoritative_ns = dig_proc.stdout.partition('\n')[0]
		return authoritative_ns

	#------------------------------------
	# current_registered_ip
	#-------------------

	def current_registered_ip(self) -> str:
		'''
		Return the IP address the DNS service currently
		knows and serves for self.host on this LAN.

		:return IP address currently held by DNS service
		:rtype str
		:raises RuntimeError if DNS server not found, or 
			currently registered IP cannot be obtained.
		'''
		# Could raise RuntimeError if fails to find server:
		dns_server = self.get_dns_server(self.domain)

		dig_a_cmd = [
			self.dig_binary, 'a', f"{self.host}.{self.domain}", 
			f"@{dns_server}", '+short'
		]
		dig_proc = subprocess.run(dig_a_cmd, capture_output=True, text=True)
		if dig_proc.returncode != 0:
			msg = (f"DDNS update on {dns_server} for host {self.host} failed; \n"
		  		   "could not obtain currently registered IP (A record): \n"
				   f"{dig_proc.stderr}.")
			raise RuntimeError(msg)
		
		cur_registered_ip = dig_proc.stdout.rstrip()
		return cur_registered_ip
	
	#------------------------------------
	# cur_own_ip
	#-------------------	

	def cur_own_ip(self) -> str:
		'''
		Return the IP which outgoing packets 
        list as origin IP.
		
		:return: IP listed as orginator in outgoing packets
		:rtype: str
		:raises RuntimeError: if request to echo own IP fails
		'''
		own_ip_url = DDNSUpdater.WHATS_MY_IP_URL
		try:
			own_ip = self.fetch_flex(own_ip_url, user_agent='curl')
		except Exception as e:
			msg = (f"DDNS update script failed to obtain current IP "
					f"via URL {own_ip_url}: {e}")
			self.logger.error(msg)
			return
		return own_ip

	#------------------------------------
	# fetch_flex
	#-------------------

	def fetch_flex(self, url, timeout=30, user_agent='python'):
		'''
		Flexible Web access via a URL.
		
		Issue an HTTP request, optionally behaving like
		the OS level curl command. Curl contacts servers
		as a special user agent, to which servers may 
		return differently formatted results.

		For example: a what's-my-ip server like laxa.org 
		returns an HTML page if called by Python's default
		headers. But returns a simple "<ip-str>\n" if it
		believes to be called by curl.

		To have get() calls look like a 'regular' Python program,
		set the user_agent keyword to 'python'. To have returns
		look like the curl command, set user_agent='curl'

		:param url: URL to contact
		:type url: str
		:param timeout: timeout in seconds, defaults to 30
		:type timeout: int, optional
		:param user_agent: whether to behave like curl, or Python code, defaults to 'python'
		:type user_agent: str, optional
		:returns: text with white space trimmed; could be JSON, could be HTML, or plain text
		:rtype: str
		:raises ConnectionError: DNS failure, refused connection, etc.
		:raises TimeoutError: timeout occurred
		:raises ValueError: for client error
		:raises RuntimeError: for server-side error
		:raises RuntimeError: any other error
		'''
		try:
			if user_agent == 'curl':
				headers = {
					'User-Agent': 'curl/7.68.0',
					'Accept': '*/*'
				}
				response = requests.get(url, headers=headers, timeout=timeout)
			else:
				response = requests.get(url, timeout=timeout)
			# Raise HTTPError for bad status codes
			response.raise_for_status()
			resp_txt = response.text.strip() if user_agent == 'curl' \
											 else response.text
			return resp_txt

  		# Be explicit about the type of error:
		except ConnectionError:
			# Network problem (DNS failure, refused connection, etc.)
			raise ConnectionError(f"Failed to connect to {url}")
			
		except Timeout:
			# Request timed out
			raise TimeoutError(f"Request to {url} timed out after {timeout} seconds")
			
		except HTTPError as e:
			# HTTP error status codes (4xx, 5xx)
			status_code = e.response.status_code
			if 400 <= status_code < 500:
				raise ValueError(f"Client error {status_code} for URL {url}")
			else:
				raise RuntimeError(f"Server error {status_code} for URL {url}")
				
		except RequestException as e:
			# Catch-all for other requests-related errors
			raise RuntimeError(f"Request failed for {url}: {str(e)}")			
			

	#------------------------------------
	# setup_logging
	#-------------------

	def setup_logging(
			self, 
			file_path: str, 
			max_file_sz: int, 
			num_files: int) -> logging.Logger:
		'''
		Prepare logging to files, limiting the maximum
		size of each log file, and rotating among num_files
		files. If file_path is
		    .../ddns_updates.log
		The rotation files will be called
			.../ddns_updates.log
			.../ddns_updates.log.1
			.../ddns_updates.log.2
			   ...

		Log entries will look like:
		   2023-10-27 10:30:00,123 - root - INFO - Application started.

		Use the returned logger like:

			logger.info("Application started")
			logger.error("Bad stuff happened")
			logger.warning("Could be worse")

		:param file_path: path to the log file
		:type file_path: str
		:param max_file_sz: maximum size to which each log file may grow
		:type max_file_sz: int
		:param num_files: number of log files to rotate between
		:type num_files: int
		:return: a new logger instance
		:rtype: logging.Logger
		'''

		# Ensure that the logfile directory 
		# exists; but OK if already does:
		Path.mkdir(Path(file_path).parent, exist_ok=True)

	    # Create a logger
		logger = logging.getLogger(__name__)
		logger.setLevel(logging.INFO)

		# Create a RotatingFileHandler
		handler = RotatingFileHandler(
			file_path,
			max_file_sz,
			num_files
		)

		# Create a formatter; generates entries like:
		#  2023-10-27 10:30:00,123 - root - INFO - Application started.
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

		# Set the formatter for the handler
		handler.setFormatter(formatter)

		# Add the handler to the logger
		logger.addHandler(handler)

		return logger
	
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

def main():
	default_init_path = str(Path(__file__).parent.joinpath('ddns.ini'))
	parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description="Regularly update DDNS service with new IP, if needed"
                                     )

	parser.add_argument('-d', '--debug',
						action='store_true',
                        help="ability to run without sudo, but no DDNS update occurs",
						default=False
    )
	parser.add_argument('-l', '--list',
						action='store_true',
                        help="print list of DDNS service names",
						default=False
    )
	parser.add_argument('-c', '--config_path',
						default=default_init_path,
                        help=f"Path to the .ini DDNS service(s) config file; default: {default_init_path}"
    )
	parser.add_argument('service_nm',
                        help="Name of DDNS service to keep updated, such as 'namecheap'"
    )
	args = parser.parse_args()
    # Provide all problems in one run:
	errors = []
    # Config file exists?
	if not os.path.exists(args.config_path):
		errors.append(f"Config file {args.config_path} not found")

	# Running as sudo? Required unless --debug flag:
	if os.geteuid() != 0 and not args.debug:
		errors.append(f"Program {sys.argv[0]} must run as sudo")
	if len(errors) > 0:
		print("Problems:")
		for err_msg in errors:
			print(f"   {err_msg}")
		sys.exit(1)

	updater = DDNSUpdater(args.service_nm, args.config_path, debug=args.debug)
	if args.list:
		for service_nm in updater.services_list():
			print(service_nm)


# ------------------------ Main ------------
if __name__ == '__main__':
	main()

