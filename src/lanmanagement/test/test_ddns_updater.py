#!/usr/bin/env python3
# **********************************************************
#
# @Author: Anthropic Claude
# @Date:   2025-09-20 14:02:36
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/tests/test_ddns_updater.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-22 09:53:20
#
# **********************************************************

"""
Unit tests for DDNSUpdater class.
Tests all major functionality using mocking to isolate units under test.
"""

import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock
import tempfile
import os
import sys
from pathlib import Path
import logging
import subprocess

# Add the src directory to the path to import the module under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from lanmanagement import ddns_updater
from lanmanagement.ddns_updater import DDNSUpdater

class TestDDNSUpdater(unittest.TestCase):
    """Test cases for DDNSUpdater class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.service_name = 'namecheap'
        self.config_file = '/path/to/config.ini'
        
        # Mock the service adapter to avoid file dependencies
        self.mock_service_adapter = Mock()
        self.mock_service_adapter.get_update_url.return_value = 'http://example.com/update?ip=1.2.3.4'
        
        # Patch the DDNSServiceAdapter to return our mock
        self.ddns_adapter_patcher = patch('ddns_updater.DDNSServiceAdapter')
        self.mock_ddns_adapter_class = self.ddns_adapter_patcher.start()
        self.mock_ddns_adapter_instance = Mock()
        self.mock_ddns_adapter_instance.get_service_adapter.return_value = self.mock_service_adapter
        self.mock_ddns_adapter_class.return_value = self.mock_ddns_adapter_instance

    def tearDown(self):
        """Clean up after each test method."""
        self.ddns_adapter_patcher.stop()

    @patch('ddns_updater.shutil.which')
    @patch('ddns_updater.Path.mkdir')
    def test_init_success(self, mock_mkdir, mock_which):
        """Test successful initialization of DDNSUpdater."""
        # Mock that both dig and curl are found
        mock_which.side_effect = lambda x: '/usr/bin/' + x if x in ['dig', 'curl'] else None
        
        with patch.object(DDNSUpdater, 'setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger
            
            updater = DDNSUpdater(self.service_name, self.config_file)
            
            self.assertEqual(updater.service_nm, self.service_name)
            self.assertEqual(updater.dig_binary, '/usr/bin/dig')
            self.assertEqual(updater.curl_binary, '/usr/bin/curl')
            self.assertEqual(updater.service_adapter, self.mock_service_adapter)

    @patch('ddns_updater.shutil.which')
    @patch('ddns_updater.sys.exit')
    def test_init_missing_dig(self, mock_exit, mock_which):
        """Test initialization fails when dig is not found."""
        # Mock that dig is not found but curl is
        mock_which.side_effect = lambda x: '/usr/bin/curl' if x == 'curl' else None
        
        with patch.object(DDNSUpdater, 'setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger
            
            DDNSUpdater(self.service_name, self.config_file)
            
            mock_logger.error.assert_called_with("Could not find needed command 'dig'")
            mock_exit.assert_called_with(1)

    @patch('ddns_updater.shutil.which')
    @patch('ddns_updater.sys.exit')
    def test_init_missing_curl(self, mock_exit, mock_which):
        """Test initialization fails when curl is not found."""
        # Mock that curl is not found but dig is
        mock_which.side_effect = lambda x: '/usr/bin/dig' if x == 'dig' else None
        
        with patch.object(DDNSUpdater, 'setup_logging') as mock_setup_logging:
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger
            
            DDNSUpdater(self.service_name, self.config_file)
            
            mock_logger.error.assert_called_with("Could not find needed command 'curl'")
            mock_exit.assert_called_with(1)

    def _create_test_updater(self):
        """Helper method to create a DDNSUpdater instance for testing."""
        with patch('ddns_updater.shutil.which') as mock_which, \
             patch.object(DDNSUpdater, 'setup_logging') as mock_setup_logging:
            
            mock_which.side_effect = lambda x: '/usr/bin/' + x if x in ['dig', 'curl'] else None
            mock_logger = Mock()
            mock_setup_logging.return_value = mock_logger
            
            updater = DDNSUpdater(self.service_name, self.config_file)
            updater.host = 'test'
            updater.domain = 'example.com'
            return updater

    @patch('ddns_updater.subprocess.run')
    def test_get_dns_server_success(self, mock_run):
        """Test successful DNS server retrieval."""
        updater = self._create_test_updater()
        
        # Mock successful dig command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'dns1.namecheaphosting.com.\ndns2.namecheaphosting.com.\n'
        mock_run.return_value = mock_result
        
        dns_server = updater.get_dns_server('example.com')
        
        self.assertEqual(dns_server, 'dns1.namecheaphosting.com.')
        mock_run.assert_called_with(['/usr/bin/dig', 'ns', 'example.com', '+short'], 
                                   capture_output=True, text=True)

    @patch('ddns_updater.subprocess.run')
    def test_get_dns_server_failure(self, mock_run):
        """Test DNS server retrieval failure."""
        updater = self._create_test_updater()
        
        # Mock failed dig command
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = 'Domain not found'
        mock_run.return_value = mock_result
        
        with self.assertRaises(RuntimeError) as context:
            updater.get_dns_server('example.com')
        
        self.assertIn('failed to identify authoritative NS', str(context.exception))

    @patch('ddns_updater.subprocess.run')
    def test_current_registered_ip_success(self, mock_run):
        """Test successful current registered IP retrieval."""
        updater = self._create_test_updater()
        
        # Mock two subprocess calls: first for DNS server, second for A record
        mock_results = [
            Mock(returncode=0, stdout='dns1.example.com.\n'),  # DNS server query
            Mock(returncode=0, stdout='192.168.1.100\n')       # A record query
        ]
        mock_run.side_effect = mock_results
        
        ip = updater.current_registered_ip()
        
        self.assertEqual(ip, '192.168.1.100')
        self.assertEqual(mock_run.call_count, 2)

    @patch('ddns_updater.subprocess.run')
    def test_current_registered_ip_dns_failure(self, mock_run):
        """Test current registered IP retrieval fails when DNS server lookup fails."""
        updater = self._create_test_updater()
        
        # Mock failed DNS server lookup
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = 'DNS lookup failed'
        mock_run.return_value = mock_result
        
        with self.assertRaises(RuntimeError):
            updater.current_registered_ip()

    @patch('ddns_updater.subprocess.run')
    def test_current_registered_ip_a_record_failure(self, mock_run):
        """Test current registered IP retrieval fails when A record lookup fails."""
        updater = self._create_test_updater()
        
        # Mock successful DNS server lookup, failed A record lookup
        mock_results = [
            Mock(returncode=0, stdout='dns1.example.com.\n'),  # DNS server query succeeds
            Mock(returncode=1, stderr='A record not found')     # A record query fails
        ]
        mock_run.side_effect = mock_results
        
        with self.assertRaises(RuntimeError) as context:
            updater.current_registered_ip()
        
        self.assertIn('could not obtain currently registered IP', str(context.exception))

    @patch('ddns_updater.subprocess.run')
    def test_cur_own_ip_success(self, mock_run):
        """Test successful current own IP retrieval."""
        updater = self._create_test_updater()
        
        # Mock successful curl command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '203.0.113.42\n'
        mock_run.return_value = mock_result
        
        ip = updater.cur_own_ip()
        
        self.assertEqual(ip, '203.0.113.42')
        mock_run.assert_called_with(['/usr/bin/curl', 'https://4.laxa.org'], 
                                   capture_output=True, text=True)

    @patch('ddns_updater.subprocess.run')
    def test_cur_own_ip_failure(self, mock_run):
        """Test current own IP retrieval failure."""
        updater = self._create_test_updater()
        
        # Mock failed curl command
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = 'Connection failed'
        mock_run.return_value = mock_result
        
        with self.assertRaises(RuntimeError) as context:
            updater.cur_own_ip()
        
        self.assertIn('failed to cURL public IP', str(context.exception))

    @patch('ddns_updater.subprocess.run')
    def test_report_own_ip_no_change(self, mock_run):
        """Test report_own_ip when IP hasn't changed."""
        updater = self._create_test_updater()
        
        # Mock that both current own IP and registered IP are the same
        mock_results = [
            Mock(returncode=0, stdout='203.0.113.42\n'),        # cur_own_ip
            Mock(returncode=0, stdout='dns1.example.com.\n'),   # get_dns_server
            Mock(returncode=0, stdout='203.0.113.42\n')         # current_registered_ip
        ]
        mock_run.side_effect = mock_results
        
        updater.report_own_ip()
        
        # Should not call the update URL since IPs are the same
        self.mock_service_adapter.get_update_url.assert_not_called()

    @patch('ddns_updater.subprocess.run')
    def test_report_own_ip_with_change(self, mock_run):
        """Test report_own_ip when IP has changed."""
        updater = self._create_test_updater()
        
        # Mock different IPs and successful update
        mock_results = [
            Mock(returncode=0, stdout='203.0.113.42\n'),        # cur_own_ip
            Mock(returncode=0, stdout='dns1.example.com.\n'),   # get_dns_server  
            Mock(returncode=0, stdout='192.168.1.100\n'),       # current_registered_ip
            Mock(returncode=0, stdout='OK')                     # curl update
        ]
        mock_run.side_effect = mock_results
        
        updater.report_own_ip()
        
        # Should call the service adapter to get update URL
        self.mock_service_adapter.get_update_url.assert_called_with('203.0.113.42')
        
        # Should log the successful update
        updater.logger.info.assert_called_with('Reported updated 192.168.1.100 => 203.0.113.42')

    @patch('ddns_updater.subprocess.run')
    def test_report_own_ip_update_failure(self, mock_run):
        """Test report_own_ip when the update curl fails."""
        updater = self._create_test_updater()
        
        # Mock different IPs but failed update
        mock_results = [
            Mock(returncode=0, stdout='203.0.113.42\n'),        # cur_own_ip
            Mock(returncode=0, stdout='dns1.example.com.\n'),   # get_dns_server
            Mock(returncode=0, stdout='192.168.1.100\n'),       # current_registered_ip
            Mock(returncode=1, stderr='Update failed')          # curl update fails
        ]
        mock_run.side_effect = mock_results
        
        updater.report_own_ip()
        
        # Should log the error
        updater.logger.error.assert_called()
        error_call = updater.logger.error.call_args[0][0]
        self.assertIn('DDNS update script failed to cUrl', error_call)

    @patch('ddns_updater.Path.mkdir')
    @patch('ddns_updater.RotatingFileHandler')
    def test_setup_logging(self, mock_handler_class, mock_mkdir):
        """Test logging setup."""
        updater = self._create_test_updater()
        
        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler
        
        logger = updater.setup_logging('/tmp/test.log', 1024, 5)
        
        # Verify directory creation was attempted
        mock_mkdir.assert_called_once()
        
        # Verify handler was created with correct parameters
        mock_handler_class.assert_called_once_with('/tmp/test.log', 1024, 5)
        
        # Verify handler was configured
        mock_handler.setFormatter.assert_called_once()
        
        # Verify logger was configured
        self.assertEqual(logger.level, logging.INFO)

    def test_check_domain_syntax_valid_domains(self):
        """Test check_domain_syntax with valid domain names."""
        valid_domains = [
            'example.com',
            'subdomain.example.com',
            'test-domain.co.uk',
            'a.b.c.d.example.org',
            '123domain.com',
            'xn--n3h.com',  # IDN example
        ]
        
        for domain in valid_domains:
            with self.subTest(domain=domain):
                self.assertTrue(DDNSUpdater.check_domain_syntax(domain))

    def test_check_domain_syntax_invalid_domains(self):
        """Test check_domain_syntax with invalid domain names."""
        invalid_domains = [
            '',                          # empty string
            None,                        # None
            123,                         # not a string
            'example',                   # no TLD
            '.example.com',              # starts with dot
            'example.com.',              # ends with dot (technically valid but our regex doesn't allow)
            '-example.com',              # starts with hyphen
            'example-.com',              # label ends with hyphen
            'example..com',              # double dot
            'a' * 254 + '.com',         # too long overall
            'a' * 64 + '.com',          # label too long
            'example.c',                 # TLD too short
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.assertFalse(DDNSUpdater.check_domain_syntax(domain))


class TestDDNSUpdaterMain(unittest.TestCase):
    """Test cases for the main function and argument parsing."""

    @patch('ddns_updater.os.path.exists')
    @patch('ddns_updater.os.geteuid')
    @patch('ddns_updater.sys.exit')
    def test_main_missing_config_file(self, mock_exit, mock_geteuid, mock_exists):
        """Test main function with missing config file."""
        mock_exists.return_value = False
        mock_geteuid.return_value = 0  # Running as root
        
        # Mock sys.argv
        test_args = ['ddns_updater.py', 'namecheap', '/nonexistent/config.ini']
        with patch('ddns_updater.sys.argv', test_args):
            with patch('ddns_updater.argparse.ArgumentParser.parse_args') as mock_parse_args:
                mock_args = Mock()
                mock_args.service_nm = 'namecheap'
                mock_args.config_path = '/nonexistent/config.ini'
                mock_parse_args.return_value = mock_args
                
                # Import and run the main section
                import ddns_updater
                
                mock_exit.assert_called_with(1)

    @patch('ddns_updater.os.path.exists')
    @patch('ddns_updater.os.geteuid')
    @patch('ddns_updater.sys.exit')
    def test_main_not_running_as_sudo(self, mock_exit, mock_geteuid, mock_exists):
        """Test main function when not running as sudo."""
        mock_exists.return_value = True
        mock_geteuid.return_value = 1000  # Not running as root
        
        # Mock sys.argv
        test_args = ['ddns_updater.py', 'namecheap', '/path/to/config.ini']
        with patch('ddns_updater.sys.argv', test_args):
            with patch('ddns_updater.argparse.ArgumentParser.parse_args') as mock_parse_args:
                mock_args = Mock()
                mock_args.service_nm = 'namecheap'
                mock_args.config_path = '/path/to/config.ini'
                mock_parse_args.return_value = mock_args
                
                # Import and run the main section
                import ddns_updater
                
                mock_exit.assert_called_with(1)


if __name__ == '__main__':
    # Create a test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestDDNSUpdater))
    suite.addTest(unittest.makeSuite(TestDDNSUpdaterMain))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
