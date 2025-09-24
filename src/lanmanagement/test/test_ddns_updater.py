#!/usr/bin/env python3

# **********************************************************
#
# @Author: Andreas Paepcke
# @Date:   2025-09-24 10:09:58
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/test/test_ddns_updater.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-24 15:13:12
#
# **********************************************************

import unittest
import tempfile
from tempfile import TemporaryDirectory
import os
import sys
import logging
import configparser
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call, mock_open

# Assuming the module is in the same directory or properly importable
from lanmanagement.ddns_updater import DDNSUpdater


class TestDDNSUpdater(unittest.TestCase):
    """Test cases for DDNSUpdater class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, 'test_ddns.ini')
        self.secrets_file = os.path.join(self.test_dir, 'test_secret.txt')
        self.log_dir = os.path.join(self.test_dir, 'logs')
        
        # Create log directory
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create a test config file
        config = configparser.ConfigParser()
        config['namecheap'] = {
            'url_root': 'https://dynamicdns.park-your-domain.com/update?',
            'host': 'testhost',
            'domain': 'testdomain.com',
            'secrets_file': self.secrets_file
        }
        
        with open(self.config_file, 'w') as f:
            config.write(f)
        
        # Create a test secrets file
        with open(self.secrets_file, 'w') as f:
            f.write('test_secret_password')

    def tearDown(self):
        """Clean up after each test method."""
        # Clean up temporary files
        try:
            self.ddns_tmp_dir.cleanup()
        except AttributeError:
            # No temp dir was created with a 
            # valid .ini and a secrets pwd,
            # i.e. make_ini_file_and_secret() was
            # not called during the previous test:
            pass
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.DDNSServiceManager')
    def test_init_success(self, mock_service_manager, mock_which):
        """Test successful initialization of DDNSUpdater"""
        # Mock the required binaries
        mock_which.side_effect = lambda x: f'/usr/bin/{x}' if x in ['dig', 'curl'] else None
        
        # Mock the service manager and adapter
        mock_manager_instance = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.service_options.return_value = {
            'host': 'testhost',
            'domain': 'testdomain.com'
        }
        mock_manager_instance.get_service_adapter.return_value = mock_adapter
        mock_service_manager.return_value = mock_manager_instance
        
        with patch.object(DDNSUpdater, 'report_own_ip'):
            updater = DDNSUpdater('namecheap', self.config_file, debug=True)
        
        self.assertEqual(updater.service_nm, 'namecheap')
        self.assertTrue(updater.debug)
        self.assertEqual(updater.host, 'testhost')
        self.assertEqual(updater.domain, 'testdomain.com')
        self.assertEqual(updater.dig_binary, '/usr/bin/dig')
        self.assertEqual(updater.curl_binary, '/usr/bin/curl')

    @patch('lanmanagement.ddns_updater.shutil.which')
    @patch('lanmanagement.ddns_updater.sys.exit')
    @patch.object(DDNSUpdater, 'current_registered_ip')
    def test_init_missing_dig_binary(
        self, 
        mock_current_registered_ip, 
        mock_exit, mock_which):
        """Test initialization when dig binary is missing"""
        # Mock dig as missing, curl as present
        mock_which.side_effect = lambda x: '/usr/bin/curl' if x == 'curl' else None
        # Set the return value for the mocked method
        mock_current_registered_ip.return_value = "192.168.1.100"        
        DDNSUpdater('namecheap', self.config_file, debug=True)
        
        mock_exit.assert_called_once_with(1)

    def test_setup_logging(self):
        """Test setup_logging method"""
        log_file = os.path.join(self.test_dir, 'test.log')
        max_size = 1024
        backup_count = 3
        
        with patch.object(DDNSUpdater, 'report_own_ip'):
            updater = DDNSUpdater.__new__(DDNSUpdater)  # Create without calling __init__
            logger = updater.setup_logging(log_file, max_size, backup_count)
        
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.level, logging.INFO)
        
        # Test that log directory is created
        self.assertTrue(os.path.exists(os.path.dirname(log_file)))
        
        # Test logging functionality
        logger.info("Test message")
        self.assertTrue(os.path.exists(log_file))


class TestDDNSUpdaterStaticMethods(unittest.TestCase):
    """Test static methods of DDNSUpdater class"""

    def test_check_domain_syntax_valid_domains(self):
        """Test check_domain_syntax with valid domain names"""
        valid_domains = [
            'example.com',
            'subdomain.example.com',
            'test-domain.org',
            'multi.level.subdomain.example.net',
            'a.co',  # Minimum valid domain
            '123domain.com',  # Starting with numbers
            'domain123.com',  # Ending with numbers
            'my-site.example.info'
        ]
        
        for domain in valid_domains:
            with self.subTest(domain=domain):
                result = DDNSUpdater.check_domain_syntax(domain)
                self.assertTrue(result, f"Domain '{domain}' should be valid")

    def test_check_domain_syntax_invalid_domains(self):
        """Test check_domain_syntax with invalid domain names"""
        invalid_domains = [
            '',  # Empty string
            'example',  # No TLD
            '.example.com',  # Starting with dot
            'example.com.',  # Ending with dot
            '-example.com',  # Starting with hyphen
            'example-.com',  # Label ending with hyphen
            'ex..ample.com',  # Double dots
            'a.b',  # TLD too short
            'example.c',  # TLD too short
            'example com',  # Space in domain
            'example@com',  # Invalid character
            'a' * 64 + '.com',  # Label too long (>63 chars)
            'a' * 250 + '.com'  # Domain too long (>253 chars total)
        ]
        
        for domain in invalid_domains:
            with self.subTest(domain=domain):
                result = DDNSUpdater.check_domain_syntax(domain)
                self.assertFalse(result, f"Domain '{domain}' should be invalid")

    def test_check_domain_syntax_non_string_input(self):
        """Test check_domain_syntax with non-string inputs"""
        invalid_inputs = [
            None,
            123,
            [],
            {},
            True
        ]
        
        for invalid_input in invalid_inputs:
            with self.subTest(input=invalid_input):
                result = DDNSUpdater.check_domain_syntax(invalid_input)
                self.assertFalse(result, f"Non-string input '{invalid_input}' should be invalid")


class TestDDNSUpdaterMainFunction(unittest.TestCase):
    """Test the main function and command line argument parsing"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, 'test_ddns.ini')
        
        # Create a test config file
        config = configparser.ConfigParser()
        config['namecheap'] = {
            'url_root': 'https://dynamicdns.park-your-domain.com/update?',
            'host': 'testhost',
            'domain': 'testdomain.com',
            'secrets_file': '/tmp/secret.txt'
        }
        
        with open(self.config_file, 'w') as f:
            config.write(f)

    def tearDown(self):
        """Clean up after tests"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('lanmanagement.ddns_updater.DDNSUpdater')
    @patch('lanmanagement.ddns_updater.os.geteuid')
    @patch('lanmanagement.ddns_updater.os.path.exists')
    @patch('lanmanagement.ddns_updater.sys.argv', 
           ['lanmanagement.ddns_updater.py', 
            '-c', '/tmp/config.ini', 
            'namecheap'])
    def test_main_success_as_root(self, mock_exists, mock_geteuid, mock_ddns_updater):
        """Test main function with valid arguments and running as root"""
        from lanmanagement.ddns_updater import main
        
        mock_exists.return_value = True  # Config file exists
        mock_geteuid.return_value = 0    # Running as root
        
        main()
        
        mock_ddns_updater.assert_called_once_with(
            'namecheap',
            '/tmp/config.ini',
            debug=False)

    @patch('lanmanagement.ddns_updater.DDNSUpdater')
    @patch('lanmanagement.ddns_updater.os.geteuid')
    @patch('lanmanagement.ddns_updater.os.path.exists')
    @patch('lanmanagement.ddns_updater.sys.argv', 
           ['lanmanagement.ddns_updater.py', 
            '--debug', 
            '-c', '/tmp/config.ini', 
            'namecheap'])
    def test_main_success_debug_mode(self, mock_exists, mock_geteuid, mock_ddns_updater):
        """Test main function with debug flag"""
        from lanmanagement.ddns_updater import main
        
        mock_exists.return_value = True  # Config file exists
        mock_geteuid.return_value = 1000 # Not running as root, but debug mode
        
        main()
        
        mock_ddns_updater.assert_called_once_with(
            'namecheap', '/tmp/config.ini', debug=True)

    @patch('lanmanagement.ddns_updater.sys.exit')
    @patch('lanmanagement.ddns_updater.os.geteuid')
    @patch('lanmanagement.ddns_updater.os.path.exists')
    @patch('lanmanagement.ddns_updater.sys.argv', 
           ['lanmanagement.ddns_updater.py', 
            '-c', '/nonexistent/config.ini', 
            'namecheap'])
    @patch('builtins.print')
    def test_main_config_file_not_found(self, mock_print, mock_exists, mock_geteuid, mock_exit):
        """Test main function when config file doesn't exist"""
        from lanmanagement.ddns_updater import main
        
        mock_exists.return_value = False  # Config file doesn't exist
        mock_geteuid.return_value = 0     # Running as root
        
        with self.assertRaises(FileNotFoundError):
            main()
        
        # Actually called three times in the main() call above
        # mock_exit.assert_called_once_with(1)
        # Check that error message was printed
        print_calls = [call.args[0] for call in mock_print.call_args_list if call.args]
        config_error = any("Config file /nonexistent/config.ini not found" in msg for msg in print_calls)
        self.assertTrue(config_error, "Should print config file not found error")

    @patch('lanmanagement.ddns_updater.sys.exit')
    @patch('lanmanagement.ddns_updater.os.geteuid')
    @patch('lanmanagement.ddns_updater.os.path.exists')
    @patch('lanmanagement.ddns_updater.sys.argv', 
           ['lanmanagement.ddns_updater.py', 
            '-c', '/tmp/config.ini',
            'namecheap'])
    @patch('builtins.print')
    def test_main_not_running_as_root(self, mock_print, mock_exists, mock_geteuid, mock_exit):
        """Test main function when not running as root and not in debug mode"""
        from lanmanagement.ddns_updater import main
        
        mock_exists.return_value = True  # Config file exists
        mock_geteuid.return_value = 1000 # Not running as root

        # Ensure that a valid config file exists, so 
        # that its absence or emptiness does not preempt
        # the test:
        ddns_config_path = self.make_ini_file_and_secret()
        # The mocked sys.argv is now:
        #   [
        #       'lanmanagement.ddns_updater.py',
        #       '-c', '/tmp/config.ini',
        #       'namecheap'
        #    ]
        # Replace the ini path with the one we created
        sys.argv[-2] = ddns_config_path 
        main()
        
        mock_exit.assert_called_once_with(1)
        # Check that error message was printed
        print_calls = [call.args[0] for call in mock_print.call_args_list if call.args]
        sudo_error = any("must run as sudo" in msg for msg in print_calls)
        self.assertTrue(sudo_error, "Should print sudo requirement error")

    # ----------------- Utilities --------------
    def make_ini_file_and_secret(self):

        self.ddns_tmp_dir = TemporaryDirectory(
            dir='/tmp', 
            prefix='ddns_tmp_')
        tmp_dir_nm = self.ddns_tmp_dir.name
        config_path = os.path.join(tmp_dir_nm, 'ddns.ini')
        secrets_path = os.path.join(tmp_dir_nm, 'ddns_secret')
        config_data = {
            'namecheap': {
                'host': 'myhost',
                'domain': 'mydomain.com',
                'url_root': 'https://dynamicdns.park-your-domain.com/update?',
                'secrets_file' : secrets_path
            }
        }
        # Populate the config file:
        config = configparser.ConfigParser()
        config.read_dict(config_data)
        with open(config_path, 'w') as fd:
            config.write(fd)
            
        # Populate the secret:
        with open(secrets_path, 'w') as fd:
            fd.write("this is my secret\n")

        return config_path

# ---------------- Main ---------------
if __name__ == '__main__':
    # Run the tests with detailed output
    unittest.main(verbosity=2)
