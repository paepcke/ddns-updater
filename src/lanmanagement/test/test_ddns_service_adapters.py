#!/usr/bin/env python3

# **********************************************************
#
# @Author: Claude of Anthropic
# @Date:   2025-09-22 08:00:00
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/test/test_ddns_service_adapters.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-22 09:37:20
#
# **********************************************************

"""
Unit tests for ddns_service_adapters module.

Tests the DDNSServiceAdapter base class and NameCheap adapter implementation.
Uses temporary files and directories for configuration testing.

Test Structure
TestDDNSServiceAdapter: Tests the base class functionality including:

Configuration file handling (valid/invalid files)
Service adapter factory method
Secret retrieval from files
Path expansion with tildes and environment variables

TestNameCheap: Tests the NameCheap adapter implementation:

Proper instantiation through factory (direct instantiation forbidden)
URL generation for DDNS updates
Error handling for missing configuration options

TestAdapterRegistry: Tests the automatic adapter registration mechanism.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
import configparser

# Import the module under test
from lanmanagement.ddns_service_adapters import DDNSServiceAdapter, NameCheap


class TestDDNSServiceAdapter(unittest.TestCase):
    """Test cases for the DDNSServiceAdapter base class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_ddns.ini"
        self.secrets_file = Path(self.temp_dir) / "test_secret.txt"
        
    def tearDown(self):
        """Clean up after each test method."""
        # Clean up temporary files
        for file_path in [self.config_file, self.secrets_file]:
            if file_path.exists():
                file_path.unlink()
        os.rmdir(self.temp_dir)

    def create_test_config(self, sections_data):
        """Helper method to create a test configuration file.
        
        Args:
            sections_data (dict): Dictionary of section names to option dictionaries
        """
        config = configparser.ConfigParser()
        for section_name, options in sections_data.items():
            config.add_section(section_name)
            for key, value in options.items():
                config.set(section_name, key, value)
        
        with open(self.config_file, 'w') as f:
            config.write(f)

    def create_test_secret(self, secret_content):
        """Helper method to create a test secrets file.
        
        Args:
            secret_content (str): Content to write to secrets file
        """
        with open(self.secrets_file, 'w') as f:
            f.write(secret_content)

    def test_init_with_custom_config(self):
        """Test initialization with custom config file."""
        self.create_test_config({
            'namecheap': {
                'url_root': 'https://dynamicdns.park-your-domain.com/update?',
                'host': 'testhost',
                'domain': 'example.com',
                'secrets_file': str(self.secrets_file)
            }
        })
        
        adapter = DDNSServiceAdapter(self.config_file)
        self.assertEqual(adapter.config_file, self.config_file)
        self.assertIsInstance(adapter.config, configparser.ConfigParser)

    def test_init_with_invalid_config_file(self):
        """Test initialization with non-existent config file."""
        invalid_path = Path(self.temp_dir) / "nonexistent.ini"
        with self.assertRaises(FileNotFoundError) as cm:
            DDNSServiceAdapter(invalid_path)
        self.assertIn("does not exist", str(cm.exception))

    def test_get_service_adapter_success(self):
        """Test successful retrieval of service adapter."""
        self.create_test_config({
            'namecheap': {
                'url_root': 'https://dynamicdns.park-your-domain.com/update?',
                'host': 'testhost',
                'domain': 'example.com',
                'secrets_file': str(self.secrets_file)
            }
        })
        
        adapter_factory = DDNSServiceAdapter(self.config_file)
        service_adapter = adapter_factory.get_service_adapter('namecheap')
        self.assertIsInstance(service_adapter, NameCheap)

    def test_get_service_adapter_no_config_section(self):
        """Test get_service_adapter with missing config section."""
        self.create_test_config({'somesection': {'someoption': 'foo'}})
        adapter_factory = DDNSServiceAdapter(self.config_file)
        with self.assertRaises(NotImplementedError) as cm:
            adapter_factory.get_service_adapter('nonexistent')
        self.assertIn("has no entry in config file", str(cm.exception))

    def test_get_service_adapter_no_implementation(self):
        """Test get_service_adapter with missing implementation class."""
        self.create_test_config({
            'unsupported': {
                'url_root': 'https://example.com',
                'host': 'testhost'
            }
        })
        
        adapter_factory = DDNSServiceAdapter(self.config_file)
        with self.assertRaises(NotImplementedError) as cm:
            adapter_factory.get_service_adapter('unsupported')
        self.assertIn("is not implemented", str(cm.exception))

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval."""
        secret_content = "test_secret_password"
        self.create_test_secret(secret_content)
        self.create_test_config({
            'namecheap': {
                'secrets_file': str(self.secrets_file)
            }
        })
        
        adapter = DDNSServiceAdapter(self.config_file)
        retrieved_secret = adapter._retrieve_secret('namecheap')
        self.assertEqual(retrieved_secret, secret_content)

    def test_retrieve_secret_no_secrets_file_option(self):
        """Test secret retrieval with missing secrets_file option."""
        self.create_test_config({
            'namecheap': {
                'host': 'testhost'
            }
        })
        
        adapter = DDNSServiceAdapter(self.config_file)
        with self.assertRaises(KeyError) as cm:
            adapter._retrieve_secret('namecheap')
        self.assertIn("No 'secrets_file' entry", str(cm.exception))

    def test_retrieve_secret_file_not_found(self):
        """Test secret retrieval with non-existent secrets file."""
        nonexistent_file = Path(self.temp_dir) / "nonexistent_secret.txt"
        self.create_test_config({
            'namecheap': {
                'secrets_file': str(nonexistent_file)
            }
        })
        
        adapter = DDNSServiceAdapter(self.config_file)
        with self.assertRaises(FileNotFoundError) as cm:
            adapter._retrieve_secret('namecheap')
        self.assertIn("Could not open secrets file", str(cm.exception))

    def test_expand_path_with_tilde(self):
        """Test path expansion with tilde."""
        adapter = DDNSServiceAdapter.__new__(DDNSServiceAdapter)  # Create without __init__
        test_path = "~/test/path"
        expanded = adapter.expand_path(test_path)
        expected = str(Path.home() / "test" / "path")
        self.assertEqual(expanded, expected)

    def test_expand_path_with_env_var(self):
        """Test path expansion with environment variables."""
        adapter = DDNSServiceAdapter.__new__(DDNSServiceAdapter)  # Create without __init__
        
        # Set a test environment variable
        test_env_var = "TEST_DDNS_PATH"
        test_env_value = "/tmp/test"
        os.environ[test_env_var] = test_env_value
        
        try:
            test_path = f"${test_env_var}/secrets"
            expanded = adapter.expand_path(test_path)
            expected = "/tmp/test/secrets"
            self.assertEqual(expanded, expected)
        finally:
            # Clean up environment variable
            del os.environ[test_env_var]

    def test_expand_path_absolute(self):
        """Test path expansion with absolute path."""
        adapter = DDNSServiceAdapter.__new__(DDNSServiceAdapter)  # Create without __init__
        test_path = "/absolute/path/test"
        expanded = adapter.expand_path(test_path)
        self.assertEqual(expanded, test_path)


class TestNameCheap(unittest.TestCase):
    """Test cases for the NameCheap adapter class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_ddns.ini"
        self.secrets_file = Path(self.temp_dir) / "test_secret.txt"

    def tearDown(self):
        """Clean up after each test method."""
        # Clean up temporary files
        for file_path in [self.config_file, self.secrets_file]:
            if file_path.exists():
                file_path.unlink()
        os.rmdir(self.temp_dir)

    def create_test_config(self, sections_data):
        """Helper method to create a test configuration file."""
        config = configparser.ConfigParser()
        for section_name, options in sections_data.items():
            config.add_section(section_name)
            for key, value in options.items():
                config.set(section_name, key, value)
        
        with open(self.config_file, 'w') as f:
            config.write(f)

    def create_test_secret(self, secret_content):
        """Helper method to create a test secrets file."""
        with open(self.secrets_file, 'w') as f:
            f.write(secret_content)

    def test_init_direct_instantiation_forbidden(self):
        """Test that direct instantiation of NameCheap is forbidden."""
        with self.assertRaises(TypeError) as cm:
            NameCheap()
        self.assertIn("must be instantiated via DDNSServiceAdapter", str(cm.exception))

    def test_ddns_update_url_success(self):
        """Test successful URL generation for DDNS update."""
        secret_content = "test_password"
        self.create_test_secret(secret_content)
        self.create_test_config({
            'namecheap': {
                'url_root': 'https://dynamicdns.park-your-domain.com/update?',
                'host': 'testhost',
                'domain': 'example.com',
                'secrets_file': str(self.secrets_file)
            }
        })
        
        adapter_factory = DDNSServiceAdapter(self.config_file)
        namecheap_adapter = adapter_factory.get_service_adapter('namecheap')
        
        test_ip = "192.168.1.100"
        expected_url = (
            "https://dynamicdns.park-your-domain.com/update?"
            "host=testhost&"
            "domain=example.com&"
            f"password={secret_content}&"
            f"ip={test_ip}"
        )
        
        result_url = namecheap_adapter.ddns_update_url(test_ip)
        self.assertEqual(result_url, expected_url)
        
    def test_ddns_update_url_missing_url_root(self):
        """Test URL generation with missing url_root config."""
        self.create_test_config({
            'namecheap': {
                'host': 'testhost',
                'domain': 'example.com',
                'secrets_file': str(self.secrets_file)
            }
        })
        
        adapter_factory = DDNSServiceAdapter(self.config_file)
        namecheap_adapter = adapter_factory.get_service_adapter('namecheap')
        
        with self.assertRaises(KeyError) as cm:
            namecheap_adapter.ddns_update_url("192.168.1.100")
        self.assertIn("has not option 'url_root'", str(cm.exception))

    def test_ddns_update_url_missing_host(self):
        """Test URL generation with missing host config."""
        self.create_test_config({
            'namecheap': {
                'url_root': 'https://dynamicdns.park-your-domain.com/update?',
                'domain': 'example.com',
                'secrets_file': str(self.secrets_file)
            }
        })
        
        adapter_factory = DDNSServiceAdapter(self.config_file)
        namecheap_adapter = adapter_factory.get_service_adapter('namecheap')
        
        with self.assertRaises(KeyError) as cm:
            namecheap_adapter.ddns_update_url("192.168.1.100")
        self.assertIn("has not option 'host'", str(cm.exception))

    def test_ddns_update_url_missing_domain(self):
        """Test URL generation with missing domain config."""
        self.create_test_config({
            'namecheap': {
                'url_root': 'https://dynamicdns.park-your-domain.com/update?',
                'host': 'testhost',
                'secrets_file': str(self.secrets_file)
            }
        })
        
        adapter_factory = DDNSServiceAdapter(self.config_file)
        namecheap_adapter = adapter_factory.get_service_adapter('namecheap')
        
        with self.assertRaises(KeyError) as cm:
            namecheap_adapter.ddns_update_url("192.168.1.100")
        self.assertIn("has not option 'domain'", str(cm.exception))

    def test_adapter_registry_auto_registration(self):
        """Test that NameCheap is automatically registered in the adapter registry."""
        self.assertIn('NameCheap'.lower(), DDNSServiceAdapter._ADAPTER_REGISTRY)
        self.assertEqual(DDNSServiceAdapter._ADAPTER_REGISTRY['namecheap'], NameCheap)

class TestAdapterRegistry(unittest.TestCase):
    """Test cases for the adapter registry mechanism."""

    def test_adapter_registry_contains_namecheap(self):
        """Test that the adapter registry contains NameCheap."""
        self.assertIn('NameCheap', DDNSServiceAdapter._ADAPTER_REGISTRY)
        self.assertEqual(DDNSServiceAdapter._ADAPTER_REGISTRY['NameCheap'], NameCheap)

    def test_custom_adapter_registration(self):
        """Test that custom adapters are automatically registered."""
        # Define a custom adapter class for testing
        class TestAdapter(DDNSServiceAdapter):
            def ddns_update_url(self, new_ip: str) -> str:
                return f"http://test.com/update?ip={new_ip}"
        
        # Verify it was automatically registered
        self.assertIn('TestAdapter', DDNSServiceAdapter._ADAPTER_REGISTRY)
        self.assertEqual(DDNSServiceAdapter._ADAPTER_REGISTRY['TestAdapter'], TestAdapter)


if __name__ == '__main__':
    unittest.main()
    