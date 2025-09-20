#!/usr/bin/env python3
# **********************************************************
#
# @Author: Daniel Paepcke
# @Date:   2025-09-19 15:03:46
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/ddns_updater.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-19 19:30:50
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
from datetime import datetime

class DDNSUpdater:

	DDNS_PASSWORD_FILE  = str(Path(f"{os.getenv('HOME')} / '.ssh/ddns_password"))
	
	DDNS_LOG_FILE      = str(Path(__file__).parent / 'logs/ddns.log')
	MAX_LOGFILE_SIZE   = 100 * 1024  # 100 KB
	BACKUP_COUNT 	   = 5
	
    # Server from which to learn one's own IP:
	WHATS_MY_IP_URL = 'https://4.laxa.org'

	#------------------------------------
	# Constructor
	#-------------------	

	def __init__(self, host: str, domain: str, period: int=0):
		'''
		Prepare for IP check-and-update workflow. Host is the
		name under which the DDNS service holds the target machine.
		Domain is the corresponding domain.

		If period not zero, it must be a positive int of minutes
		to wait between re-checking whether this machine's outgoing
		IP address has changed. If zero, the check happens immediately,
		and just once. Use zero if cron is to run this script.
		NOTE: the current implementation of recurring calls is not 
		      ideal. It uses sleep, which, for instance, prevents signal
			  processing such as cnt-C via SIGTERM. If you have cron
			  set period to 0, and use crong

		:param host: host for which DNS holds an IP
		:type host: str
		:param domain: domain of the host
		:type domain: str
		:param period: how many minutes between checking, and 
			(possibly) updating IP
		:type period: int
		'''
		self.host = host
		self.domain = domain

		self.logger = self.setup_logging(
			DDNSUpdater.DDNS_LOG_FILE,
			DDNSUpdater.MAX_LOGFILE_SIZE,
			DDNSUpdater.BACKUP_COUNT)

		# The OS level 'dig' program: obtains host infos
		self.dig_binary = shutil.which('dig')
		if self.dig_binary is None:
			self.logger.error("Could not find needed command 'dig'")
			sys.exit(1)

		# The OS level 'curl' program:
		self.curl_binary = shutil.which('curl')
		if self.curl_binary is None:
			self.logger("Could not find needed command 'curl'")
			sys.exit(1)

		if period == 0:
			self.report_own_ip()
			return
		
		# Period is number of minutes between checks:
		while True:
			# Not a good solution; use a scheduler instead
			# On Linux/MacOS use cron, and set period to 0
			self.report_own_ip()
			os.sleep(period * 60)

	#------------------------------------
	# report_own_ip
	#-------------------

	def report_own_ip(self):

		cur_own_ip = self.cur_own_ip()
		cur_registered_ip = self.current_registered_ip()
		if cur_own_ip == cur_registered_ip:
			# Nothing to report
			return
		
		self.logger.info(f"IP changed from {cur_registered_ip} to {cur_own_ip}")
		try:
			with open(DDNSUpdater.DDNS_PASSWORD_FILE, 'r') as fp:
				password = fp.readline().rstrip()
			url = \
				'https://dynamicdns.park-your-domain.com/update?' \
				f"host={self.host}&" \
				f"domain={self.domain}&" \
				f"password={password}&" \
				f"ip={cur_own_ip}"

			curl_proc = subprocess.run(
				[self.curl_binary, url], capture_output=True, text=True
			)
			if curl_proc.returncode != 0:
				msg = (f"DDNS update script failed to cUrl new A record "
		   			   f"via URL {url}: {curl_proc.stderr}")
				self.logger.error(msg)
				return
		except Exception as e:
			msg = f"Error while reporting IP: {e}"
			self.logger.error(msg)
		else:
			# Log the success:
			f"Reported updated {cur_registered_ip} => {cur_own_ip}"
			self.logger.info(msg)
		
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
		:raises RuntimeError: if OS level 'curl fails
		'''

		curl_ip_cmd = [self.curl_binary, DDNSUpdater.WHATS_MY_IP_URL]
		curl_proc = subprocess.run(curl_ip_cmd, capture_output=True, text=True)
		if curl_proc.returncode != 0:
			msg = f"DDNS update script failed to cURL public IP: {curl_proc.stderr}"
			raise RuntimeError(msg)
		
		ip = curl_proc.stdout.rstrip()
		return ip

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

# ------------------------ Main ------------
if __name__ == '__main__':
	parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
									 formatter_class=argparse.RawTextHelpFormatter,
									 description="Regularly update DDNS service with new IP, if needed"
									 )

	parser.add_argument('-p', '--period',
						help='number of minutes between checking IP, and reporting if needed; default: 10.',
						type=int,
						default=0
	),
	parser.add_argument('host',
						help=('Name of host which is registered with DDNS service'),
	)
	parser.add_argument('domain',
						help=('Domain of registered host'),
	)

	args = parser.parse_args()

	if args.period < 0:
		print(f"IP check period must be a positive int, or zero, not {args.period}")
		sys.exit(1)

	if not DDNSUpdater.check_domain_syntax(args.domain):
		print(f"Domain '{args.domain}' is not proper domain syntax")
		sys.exit(1)		
	
	
	DDNSUpdater(args.host, args.domain, args.period)