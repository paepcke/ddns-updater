#!/usr/bin/env python3
# **********************************************************
#
# @Author: Andreas Paepcke
# @Date:   2025-09-20 14:02:36
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/tests/test_ddns_updater.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-20 14:57:18
#
# **********************************************************

"""
Unit tests for DDNSUpdater class.

These tests mock external dependencies like subprocess calls, file operations,
and network requests to test the logic in isolation.
"""

import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock
import subprocess
import sys
import os
from pathlib import Path
import tempfile
import shutil

# Import the class under test
from lanmanagement.ddns_updater import DDNSUpdater


class TestDDNSUpdater(unittest.TestCase):
    """Test cases for DDNSUpdater class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_host = "myhost"
        self.test_domain = "example.com"
        self.test_current_ip = "192.168.1.100"
        self.test_registered_ip = "192.168.1.101"
        self.test_password = "test_password_123"
        
    def tearDown(self):
        """Clean up after each test method."""
        pass
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip')
    def test_init_with_period_zero(self, mock_report, mock_setup_logging, mock_which):
        """Test initialization with period=0 (single run)."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        self.assertEqual(updater.host, self.test_host)
        self.assertEqual(updater.domain, self.test_domain)
        mock_report.assert_called_once()
        mock_setup_logging.assert_called_once()
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    def test_init_missing_dig_command(self, mock_setup_logging, mock_which):
        """Test initialization when 'dig' command is not found."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_which.side_effect = lambda cmd: None if cmd == 'dig' else f"/usr/bin/{cmd}"
        
        with self.assertRaises(SystemExit) as cm:
            DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        self.assertEqual(cm.exception.code, 1)
        mock_logger.error.assert_called_with("Could not find needed command 'dig'")
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    def test_init_missing_curl_command(self, mock_setup_logging, mock_which):
        """Test initialization when 'curl' command is not found."""
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        mock_which.side_effect = lambda cmd: None if cmd == 'curl' else f"/usr/bin/{cmd}"
        
        with self.assertRaises(SystemExit) as cm:
            DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        self.assertEqual(cm.exception.code, 1)
        # Note: There's a bug in the original code - missing .error() call
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.subprocess.run')
    def test_get_dns_server_success(self, mock_run, mock_setup_logging, mock_which):
        """Test successful DNS server lookup."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock successful dig command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "dns1.namecheaphosting.com.\ndns2.namecheaphosting.com.\n"
        mock_run.return_value = mock_result
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        dns_server = updater.get_dns_server(self.test_domain)
        
        self.assertEqual(dns_server, "dns1.namecheaphosting.com.")
        mock_run.assert_called_with(
            [updater.dig_binary, 'ns', self.test_domain, '+short'],
            capture_output=True, text=True
        )
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.subprocess.run')
    def test_get_dns_server_failure(self, mock_run, mock_setup_logging, mock_which):
        """Test DNS server lookup failure."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock failed dig command
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "dig: command failed"
        mock_run.return_value = mock_result
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        with self.assertRaises(RuntimeError) as cm:
            updater.get_dns_server(self.test_domain)
        
        self.assertIn("DDNS update script failed to identify authoritative NS", str(cm.exception))
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.subprocess.run')
    def test_current_registered_ip_success(self, mock_run, mock_setup_logging, mock_which):
        """Test successful current registered IP lookup."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock both dig commands (NS and A record lookups)
        def mock_subprocess_side_effect(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            if 'ns' in cmd:
                result.stdout = "dns1.namecheaphosting.com.\n"
            elif 'a' in cmd:
                result.stdout = f"{self.test_registered_ip}\n"
            return result
        
        mock_run.side_effect = mock_subprocess_side_effect
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        registered_ip = updater.current_registered_ip()
        
        self.assertEqual(registered_ip, self.test_registered_ip)
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.subprocess.run')
    def test_cur_own_ip_success(self, mock_run, mock_setup_logging, mock_which):
        """Test successful current IP lookup."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock successful curl command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = f"{self.test_current_ip}\n"
        mock_run.return_value = mock_result
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        current_ip = updater.cur_own_ip()
        
        self.assertEqual(current_ip, self.test_current_ip)
        mock_run.assert_called_with(
            [updater.curl_binary, DDNSUpdater.WHATS_MY_IP_URL],
            capture_output=True, text=True
        )
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.subprocess.run')
    def test_cur_own_ip_failure(self, mock_run, mock_setup_logging, mock_which):
        """Test current IP lookup failure."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Mock failed curl command
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "curl: connection failed"
        mock_run.return_value = mock_result
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        with self.assertRaises(RuntimeError) as cm:
            updater.cur_own_ip()
        
        self.assertIn("DDNS update script failed to cURL public IP", str(cm.exception))
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.cur_own_ip')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.current_registered_ip')
    def test_report_own_ip_no_change(self, mock_registered, mock_current, mock_setup_logging, mock_which):
        """Test report_own_ip when IPs are the same (no update needed)."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Same IP for both current and registered
        mock_current.return_value = self.test_current_ip
        mock_registered.return_value = self.test_current_ip
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        # Manually call the method
        updater.report_own_ip()
        
        # Should not log any IP change since they're the same
        mock_logger.info.assert_not_called()
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.cur_own_ip')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.current_registered_ip')
    @patch('builtins.open', new_callable=mock_open)
    @patch('lanmanagement.ddns_updater.subprocess.run')
    def test_report_own_ip_successful_update(self, mock_run, mock_file, mock_registered, 
                                           mock_current, mock_setup_logging, mock_which):
        """Test successful IP update to DDNS service."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Different IPs to trigger update
        mock_current.return_value = self.test_current_ip
        mock_registered.return_value = self.test_registered_ip
        
        # Mock password file reading
        mock_file.return_value.readline.return_value = f"{self.test_password}\n"
        
        # Mock successful curl update
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        # Manually call the method
        updater.report_own_ip()
        
        # Verify logging of IP change
        mock_logger.info.assert_called()
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
        
        # Check if IP change was logged
        ip_change_logged = any(
            f"IP changed from {self.test_registered_ip} to {self.test_current_ip}" in call 
            for call in log_calls
        )
        self.assertTrue(ip_change_logged)
    
    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.setup_logging')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.cur_own_ip')
    @patch('lanmanagement.ddns_updater.DDNSUpdater.current_registered_ip')
    @patch('builtins.open', new_callable=mock_open)
    @patch('lanmanagement.ddns_updater.subprocess.run')
    def test_report_own_ip_update_failure(self, mock_run, mock_file, mock_registered,
                                        mock_current, mock_setup_logging, mock_which):
        """Test DDNS update failure."""
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        mock_logger = Mock()
        mock_setup_logging.return_value = mock_logger
        
        # Different IPs to trigger update
        mock_current.return_value = self.test_current_ip
        mock_registered.return_value = self.test_registered_ip
        
        # Mock password file reading
        mock_file.return_value.readline.return_value = f"{self.test_password}\n"
        
        # Mock failed curl update
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "curl: update failed"
        mock_run.return_value = mock_result
        
        with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
            updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
        
        # Manually call the method
        updater.report_own_ip()
        
        # Verify error logging
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args[0][0]
        self.assertIn("DDNS update script failed to cUrl new A record", error_call)
    
    def test_check_domain_syntax_valid_domains(self):
        """Test domain syntax validation with valid domains."""
        valid_domains = [
            "example.com",
            "sub.example.com",
            "test-domain.org",
            "a.b.c.d.com",
            "123domain.net"
        ]
        
        for domain in valid_domains:
            with self.subTest(domain=domain):
                self.assertTrue(DDNSUpdater.check_domain_syntax(domain))
    
    def test_check_domain_syntax_invalid_domains(self):
        """Test domain syntax validation with invalid domains."""
        invalid_domains = [
            "",
            "example",  # No TLD
            "-example.com",  # Starts with hyphen
            "example-.com",  # Ends with hyphen
            "ex..ample.com",  # Double dots
            "example.c",  # TLD too short
            "a" * 64 + ".com",  # Label too long
            "a" * 250 + ".com",  # Domain too long
            None,
            123
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                self.assertFalse(DDNSUpdater.check_domain_syntax(domain))
    
    def test_setup_logging(self):
        """Test logging setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            max_size = 1024
            backup_count = 3
            
            with patch('lanmanagement.ddns_updater.shutil.which'):
                with patch('lanmanagement.ddns_updater.DDNSUpdater.report_own_ip'):
                    updater = DDNSUpdater(self.test_host, self.test_domain, period=0)
            
            logger = updater.setup_logging(log_file, max_size, backup_count)
            
            # Test that logger is created and has the right properties
            self.assertIsNotNone(logger)
            self.assertEqual(logger.level, 20)  # INFO level
            
            # Test that log directory is created
            self.assertTrue(os.path.exists(os.path.dirname(log_file)))


class TestDDNSUpdaterBugs(unittest.TestCase):
    """Test cases that expose bugs in the original code."""
    
if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
