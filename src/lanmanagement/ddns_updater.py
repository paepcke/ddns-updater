#!/usr/bin/env python3
# **********************************************************
#
# @Author: Daniel Paepcke
# @Date:   2025-09-19 15:03:46
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/ddns_updater.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-30 08:34:41
# @ modified by Andreas Paepcke
#
# **********************************************************

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

import requests
from requests.exceptions import RequestException, \
								ConnectionError, \
								Timeout, \
								HTTPError

python_root = str(Path(__file__).parent.parent)
if python_root not in sys.path:
	sys.path.insert(0, python_root)

from lanmanagement.dns_service import DNSService

src_dir = str(Path(__file__).parent.parent.resolve())
if src_dir not in sys.path:
	sys.path.insert(0, src_dir)
from lanmanagement.ddns_service_adapters import DDNSServiceManager

class DDNSConfigError(Exception):
	pass

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

	def __init__(
			self, 
			service_nm: str, 
			config_file: str, 
			config_only: bool=False,
			debug: bool=False):
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

		# Obtain a DDNS service adapter that will provide
		# update URLs appropriate for the chosen service provider:
		self.ddns_srv_manager = DDNSServiceManager(config_file)
		# If all we wanted was to read the config
		# file so the caller could get info about it,
		# then we are done:
		if config_only:
			return
		
		# Get service adapter for the specific service:
		self.service_adapter = self.ddns_srv_manager.get_service_adapter(service_nm)
		
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

		try:
			self.report_own_ip()
		except DDNSConfigError as e:
			msg = f"Configuration error ({config_file}): {e}"
			self.logger.error(msg)
			print(msg)

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

		try:
			update_url = self.service_adapter.ddns_update_url(cur_own_ip)
		except Exception as e:
			# Raise a config error, so that caller
			# can give advice:
			raise DDNSConfigError(str(e)) from e

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

		service_names = self.ddns_srv_manager.services_list()
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
		# Get list of nameserver strings:
		return DNSService.get_ns_records(domain)[0]

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
		# Returns the first of potentially several nameservers:
		dns_server = self.get_dns_server(self.domain)
		
		# Returns a list of (usually one) IP addresses:
		# Could raise RuntimeError as well:
		cur_registered_ip = DNSService.get_A_records(self.domain, dns_server)[0]
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
		# exists; but OK if already does.
		# However: we often run as sudo, but want
		# the log file to have the same ownership
		# and group as this Python file, not be
		# root:
		this_file = Path(__file__)
		stats = this_file.stat()
		owner_uid = stats.st_uid
		owner_gid = stats.st_gid

		# Create logs directory
		log_dir = Path(file_path).parent
		log_dir.mkdir(mode=0o755, exist_ok=True)
		os.chown(log_dir, owner_uid, owner_gid)

		# Pre-create the log file with proper ownership and permissions
		# This ensures RotatingFileHandler doesn't create it as root
		log_file = Path(file_path)
		if not log_file.exists():
			log_file.touch()
			os.chown(log_file, owner_uid, owner_gid)
			log_file.chmod(0o644)
		
	    # Create a logger
		logger = logging.getLogger(__name__)
		logger.setLevel(logging.INFO)

	    # Use custom handler that preserves ownership
		handler = OwnershipPreservingRotatingFileHandler(
			file_path,
			maxBytes=max_file_sz,
			backupCount=num_files,
			reference_file=this_file
		)

		# Create a formatter; generates entries like:
		#  2023-10-27 10:30:00,123 - root - INFO - Application started.
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

		# Set the formatter for the handler
		handler.setFormatter(formatter)

		# Add the handler to the logger
		logger.addHandler(handler)

		return logger
	
# ----------------------- Class OwnershipPreservingRotatingFileHandler --------------

class OwnershipPreservingRotatingFileHandler(RotatingFileHandler):
	'''
	Subclass of the RotatingFileHandler does the same
	rotation of log files when they get large as the 
	parent. But even when run as root when a rotation occurs,
	any newly created log files will be owner/group the
	same as this Python file, i.e. not root.
	Purpose: even if one occasionally runs as regular user,
	e.g. with the --info or --list option, no root-only errors
	will occur.
	'''

	def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, 
					encoding=None, delay=False, reference_file=None):
		'''
		Same args and action as parent class, but additional 
		optional arg 'reference_file'. If provided, the new
		log file's owner and group will be those of the 
		reference file. Else the same ownership and group as
		this Python file's are used

		:param filename: new log's name
		:type filename: str
		:param mode: access mode, defaults to 'a'
		:type mode: str, optional
		:param maxBytes: maximum size, defaults to 0
		:type maxBytes: int, optional
		:param backupCount: number of log files in addition to current, defaults to 0
		:type backupCount: int, optional
		:param encoding: file encoding, defaults to None
		:type encoding: _type_, optional
		:param delay: if True, defers file opening till first write, defaults to False
		:type delay: bool, optional
		:param reference_file: model file for ownership and group, defaults to None
		:type reference_file: str, optional
		'''
		self.reference_file = Path(reference_file) if reference_file else Path(__file__)
		super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)

	def doRollover(self):
		"""Override to fix ownership after rotation"""
		super().doRollover()
		
		# Get reference ownership 
		# (self.reference_file is a Path)
		stats = self.reference_file.stat()
		owner_uid = stats.st_uid
		owner_gid = stats.st_gid
		
		# Fix ownership of all rotated files
		base_filename = Path(self.baseFilename)
		for i in range(1, self.backupCount + 1):
			rotated_file = Path(f"{self.baseFilename}.{i}")
			if rotated_file.exists():
				os.chown(rotated_file, owner_uid, owner_gid)
				rotated_file.chmod(0o644)
		
		# Fix ownership of current log file
		if base_filename.exists():
			os.chown(base_filename, owner_uid, owner_gid)
			base_filename.chmod(0o644)

# ----------------------- Main Function (top level) --------------
def main():

	desc = ("Regularly update DDNS service with new IP, if needed.\n"
		 	"Unless just --help, --list, or --info, must run as sudo")

	default_init_path = str(Path(__file__).parent.joinpath('ddns.ini'))
	parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description=desc
                                     )

	parser.add_argument('-d', '--debug',
						action='store_true',
                        help="ability to run without sudo, but no DDNS update occurs",
						default=False
    )
	parser.add_argument('-l', '--list',
						action='store_true',
                        help="print names of available DDNS services; then exit",
						default=False
    )
	parser.add_argument('-i', '--info',
						action='store_true',
                        help="print config info, then exit",
						default=False
    )
	parser.add_argument('-c', '--config_path',
						default=default_init_path,
                        help=(f"Path to the .ini DDNS service(s) config file;\n" 
							  f"default: {default_init_path}")
    )
	# The service name is required *unless** --list or --info
	# We enforce that after parser.parse_args():
	parser.add_argument('service_nm',
					 	nargs='?',
						default=None,
                        help=("Name of DDNS service to keep updated, such as 'namecheap'\n"
							  "Required, unless --help, --list or --info")
    )
	args = parser.parse_args()

	# Required service_nm unless --list or --info:
	if args.service_nm is None:
		if not (args.list or args.info):
			print("The DDNS service name is required without either --list or --info")
			sys.exit(1)

	# Does caller only want info on where config
	# and log info are?
	if args.info:
		print(f"Config file: {args.config_path}")
		print(f"Log files. : {DDNSUpdater.DDNS_LOG_FILE}")
		msg = (f"Default secrets path (can change in config file): " 
		 	   f"{DDNSUpdater.DDNS_PASSWORD_FILE}")
		print(msg)
		sys.exit(0)

	if args.list:
		# Init updater, but do not report new IP
		updater = DDNSUpdater(None, args.config_path, config_only=True)
		for service_nm in updater.services_list():
			print(service_nm)
		sys.exit(0)

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

	try:
		updater = DDNSUpdater(args.service_nm, args.config_path, debug=args.debug)
	except NotImplementedError as e:
		print(f"{e}. (run ddns-updater --list to see supported services)")

# ------------------------ Main ------------
if __name__ == '__main__':
	main()

