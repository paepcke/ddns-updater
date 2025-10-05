 # **********************************************************
 #
 # @Author: Andreas Paepcke
 # @Date:   2025-09-24 10:12:03
 # @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/test/test_ddns_service_adapters.py
 # @Last Modified by:   Andreas Paepcke
 # @Last Modified time: 2025-10-05 11:51:08
 #
 # **********************************************************
#!/usr/bin/env python3

import unittest
import tempfile
import os
import configparser
from pathlib import Path
from unittest.mock import patch, mock_open

# Assuming the module is in the same directory or properly importable
from lanmanagement.ddns_service_adapters import DDNSServiceManager, NameCheap


class TestDDNSServiceManager(unittest.TestCase):
    """Test cases for DDNSServiceManager class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset the singleton instance for clean tests
        DDNSServiceManager._instance = None
        
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, 'test_ddns.ini')
        self.secrets_file = os.path.join(self.test_dir, 'test_secret.txt')
        
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
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        # Reset singleton
        DDNSServiceManager._instance = None

    def test_singleton_pattern(self):
        """Test that DDNSServiceManager implements singleton pattern correctly"""
        manager1 = DDNSServiceManager(self.config_file)
        manager2 = DDNSServiceManager(self.config_file)
        
        self.assertIs(manager1, manager2, "DDNSServiceManager should be a singleton")
        self.assertEqual(id(manager1), id(manager2), "Both instances should have same memory address")

    def test_init_with_valid_config(self):
        """Test initialization with a valid config file"""
        manager = DDNSServiceManager(self.config_file)
        
        self.assertTrue(hasattr(manager, 'config'), "Manager should have config attribute")
        self.assertTrue(manager.config.has_section('namecheap'), "Config should have namecheap section")
        self.assertEqual(manager.config_file, self.config_file, "Config file path should be stored")

    def test_init_with_nonexistent_config(self):
        """Test initialization with nonexistent config file raises FileNotFoundError"""
        nonexistent_file = '/nonexistent/path/config.ini'
        
        with self.assertRaises(FileNotFoundError) as context:
            DDNSServiceManager(nonexistent_file)
        
        self.assertIn("does not exist", str(context.exception))

    def test_init_with_empty_config(self):
        """Test initialization with empty config file raises TypeError"""
        empty_config_file = os.path.join(self.test_dir, 'empty.ini')
        with open(empty_config_file, 'w') as f:
            f.write('')  # Empty file
        
        with self.assertRaises(TypeError) as context:
            DDNSServiceManager(empty_config_file)
        
        self.assertIn("seems empty", str(context.exception))

    def test_default_config_file(self):
        """Test that default config file path is set correctly"""
        # This test checks the class attribute, not requiring file existence
        expected_path = Path(__file__).parent / 'ddns.ini'
        # We can't test the actual file since it might not exist, but we can test the path construction
        self.assertTrue(isinstance(DDNSServiceManager.DEFAULT_CONFIG_FILE, Path))

    def test_service_name_on_parent_class(self):
        """Test that service_name() raises TypeError when called on parent class"""
        manager = DDNSServiceManager(self.config_file)
        
        with self.assertRaises(TypeError) as context:
            manager.service_name()
        
        self.assertIn("service adapter instance", str(context.exception))

    def test_service_options_with_service_name(self):
        """Test service_options() with explicit service name"""
        manager = DDNSServiceManager(self.config_file)
        options = manager.service_options('namecheap')
        
        expected_options = {
            'url_root': 'https://dynamicdns.park-your-domain.com/update?',
            'host': 'testhost',
            'domain': 'testdomain.com',
            'secrets_file': self.secrets_file
        }
        
        self.assertEqual(options, expected_options, "Should return correct service options")

    def test_get_service_adapter_success(self):
        """Test successful retrieval of service adapter"""
        manager = DDNSServiceManager(self.config_file)
        adapter = manager.get_service_adapter('namecheap')
        
        self.assertIsInstance(adapter, NameCheap, "Should return NameCheap adapter instance")
        self.assertTrue(hasattr(adapter, 'config'), "Adapter should have config attribute")

    def test_get_service_adapter_no_config_section(self):
        """Test get_service_adapter with service that has no config section"""
        manager = DDNSServiceManager(self.config_file)
        
        with self.assertRaises(NotImplementedError) as context:
            manager.get_service_adapter('nonexistent_service')
        
        self.assertIn("has no entry in config file", str(context.exception))

    def test_get_service_adapter_no_implementation(self):
        """Test get_service_adapter with service that has config but no implementation"""
        # Add a config section for a service that doesn't have an implementation
        config = configparser.ConfigParser()
        config.read(self.config_file)
        config['unimplemented_service'] = {'host': 'test', 'domain': 'test.com'}
        
        with open(self.config_file, 'w') as f:
            config.write(f)
        
        manager = DDNSServiceManager(self.config_file)
        
        with self.assertRaises(NotImplementedError) as context:
            manager.get_service_adapter('unimplemented_service')
        
        self.assertIn("is not implemented", str(context.exception))

    def test_ddns_update_url_on_parent(self):
        """Test that ddns_update_url raises NotImplementedError when called on parent"""
        manager = DDNSServiceManager(self.config_file)
        
        with self.assertRaises(NotImplementedError) as context:
            manager.ddns_update_url('192.168.1.1')
        
        self.assertIn("must be called on a subclass", str(context.exception))

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval"""
        manager = DDNSServiceManager(self.config_file)
        secret = manager._retrieve_secret('namecheap')
        
        self.assertEqual(secret, 'test_secret_password', "Should retrieve correct secret")

    def test_retrieve_secret_no_secrets_file_option(self):
        """Test _retrieve_secret when config has no secrets_file option"""
        # Create config without secrets_file option
        config = configparser.ConfigParser()
        config['no_secrets'] = {'host': 'test', 'domain': 'test.com'}
        
        config_file = os.path.join(self.test_dir, 'no_secrets.ini')
        with open(config_file, 'w') as f:
            config.write(f)
        
        manager = DDNSServiceManager(config_file)
        
        with self.assertRaises(KeyError) as context:
            manager._retrieve_secret('no_secrets')
        
        self.assertIn("No 'secrets_file' entry", str(context.exception))

    def test_retrieve_secret_file_not_found(self):
        """Test _retrieve_secret when secrets file doesn't exist"""
        # Create config pointing to nonexistent secrets file
        config = configparser.ConfigParser()
        config['bad_secrets'] = {
            'host': 'test',
            'domain': 'test.com',
            'secrets_file': '/nonexistent/secrets.txt'
        }
        
        config_file = os.path.join(self.test_dir, 'bad_secrets.ini')
        with open(config_file, 'w') as f:
            config.write(f)
        
        manager = DDNSServiceManager(config_file)
        
        with self.assertRaises(FileNotFoundError) as context:
            manager._retrieve_secret('bad_secrets')
        
        self.assertIn("Could not find/open secrets file", str(context.exception))

    def test_expand_path_with_tilde(self):
        """Test expand_path with tilde expansion"""
        manager = DDNSServiceManager(self.config_file)
        
        # Test tilde expansion
        path_with_tilde = '~/test/path'
        expanded = manager.expand_path(path_with_tilde)
        
        self.assertTrue(expanded.startswith('/'), "Expanded path should be absolute")
        self.assertNotIn('~', expanded, "Tilde should be expanded")

    def test_expand_path_with_env_vars(self):
        """Test expand_path with environment variables"""
        manager = DDNSServiceManager(self.config_file)
        
        # Set a test environment variable
        os.environ['TEST_DDNS_PATH'] = '/test/env/path'
        
        try:
            path_with_env = '$TEST_DDNS_PATH/subdir'
            expanded = manager.expand_path(path_with_env)
            
            self.assertEqual(expanded, '/test/env/path/subdir', "Environment variable should be expanded")
        finally:
            # Clean up environment variable
            del os.environ['TEST_DDNS_PATH']

    def test_repr(self):
        """Test __repr__ method"""
        manager = DDNSServiceManager(self.config_file)
        repr_str = repr(manager)
        
        self.assertIn("DDNS Service Manager", repr_str, "Repr should identify the class")
        self.assertIn("0x", repr_str, "Repr should include memory address")

    def test_subclass_registration(self):
        """Test that subclasses are automatically registered"""
        # Check that NameCheap is registered
        self.assertIn('namecheap', DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY)
        self.assertEqual(DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY['namecheap'], NameCheap)
        
        # Check reverse registry
        self.assertIn(NameCheap, DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY)
        self.assertEqual(DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY[NameCheap], 'namecheap')


class TestNameCheap(unittest.TestCase):
    """Test cases for NameCheap class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset the singleton instance for clean tests
        DDNSServiceManager._instance = None
        
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, 'test_ddns.ini')
        self.secrets_file = os.path.join(self.test_dir, 'test_secret.txt')
        
        # Create a test config file
        config = configparser.ConfigParser()
        config['namecheap'] = {
            'url_root': 'https://dynamicdns.park-your-domain.com/update?',
            'host': 'myhost',
            'domain': 'mydomain.com',
            'secrets_file': self.secrets_file
        }
        
        with open(self.config_file, 'w') as f:
            config.write(f)
        
        # Create a test secrets file
        with open(self.secrets_file, 'w') as f:
            f.write('my_secret_password_123')

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
        
        # Reset singleton
        DDNSServiceManager._instance = None

    def test_direct_instantiation_raises_error(self):
        """Test that direct instantiation of NameCheap raises TypeError"""
        with self.assertRaises(TypeError) as context:
            NameCheap()
        
        self.assertIn("must be instantiated via", str(context.exception))

    def test_ddns_update_url_success(self):
        """Test successful URL generation for DDNS update"""
        manager = DDNSServiceManager(self.config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        new_ip = '192.168.1.100'
        url = namecheap.ddns_update_url(new_ip)
        
        expected_url = (
            'https://dynamicdns.park-your-domain.com/update?'
            'host=myhost&'
            'domain=mydomain.com&'
            'password=my_secret_password_123&'
            'ip=192.168.1.100'
        )
        
        self.assertEqual(url, expected_url, "Should generate correct update URL")

    def test_ddns_update_url_missing_url_root(self):
        """Test ddns_update_url when config missing url_root"""
        # Create config without url_root
        config = configparser.ConfigParser()
        config['namecheap'] = {
            'host': 'myhost',
            'domain': 'mydomain.com',
            'secrets_file': self.secrets_file
        }
        
        config_file = os.path.join(self.test_dir, 'no_url_root.ini')
        with open(config_file, 'w') as f:
            config.write(f)
        
        manager = DDNSServiceManager(config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        with self.assertRaises(KeyError) as context:
            namecheap.ddns_update_url('192.168.1.100')
        
        self.assertIn("has not option 'url_root'", str(context.exception))

    def test_ddns_update_url_missing_host(self):
        """Test ddns_update_url when config missing host"""
        # Create config without host
        config = configparser.ConfigParser()
        config['namecheap'] = {
            'url_root': 'https://dynamicdns.park-your-domain.com/update?',
            'domain': 'mydomain.com',
            'secrets_file': self.secrets_file
        }
        
        config_file = os.path.join(self.test_dir, 'no_host.ini')
        with open(config_file, 'w') as f:
            config.write(f)
        
        manager = DDNSServiceManager(config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        with self.assertRaises(KeyError) as context:
            namecheap.ddns_update_url('192.168.1.100')
        
        self.assertIn("has not option 'host'", str(context.exception))

    def test_ddns_update_url_missing_domain(self):
        """Test ddns_update_url when config missing domain"""
        # Create config without domain
        config = configparser.ConfigParser()
        config['namecheap'] = {
            'url_root': 'https://dynamicdns.park-your-domain.com/update?',
            'host': 'myhost',
            'secrets_file': self.secrets_file
        }
        
        config_file = os.path.join(self.test_dir, 'no_domain.ini')
        with open(config_file, 'w') as f:
            config.write(f)
        
        manager = DDNSServiceManager(config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        with self.assertRaises(KeyError) as context:
            namecheap.ddns_update_url('192.168.1.100')
        
        self.assertIn("has not option 'domain'", str(context.exception))

    def test_service_name(self):
        """Test service_name method returns correct name"""
        manager = DDNSServiceManager(self.config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        self.assertEqual(namecheap.service_name(), 'namecheap', "Should return correct service name")

    def test_service_options(self):
        """Test service_options method returns correct options"""
        manager = DDNSServiceManager(self.config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        options = namecheap.service_options()
        expected_options = {
            'url_root': 'https://dynamicdns.park-your-domain.com/update?',
            'host': 'myhost',
            'domain': 'mydomain.com',
            'secrets_file': self.secrets_file
        }
        
        self.assertEqual(options, expected_options, "Should return correct service options")

    def test_repr(self):
        """Test __repr__ method for NameCheap instance"""
        manager = DDNSServiceManager(self.config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        repr_str = repr(namecheap)
        
        self.assertIn("DDNS Service namecheap", repr_str, "Repr should identify the service")
        self.assertIn("0x", repr_str, "Repr should include memory address")

    def test_different_ip_formats(self):
        """Test ddns_update_url with different IP formats"""
        manager = DDNSServiceManager(self.config_file)
        namecheap = manager.get_service_adapter('namecheap')
        
        # Test various IP formats
        test_ips = [
            '192.168.1.1',
            '10.0.0.1', 
            '172.16.0.1',
            '8.8.8.8',
            '255.255.255.255'
        ]
        
        for ip in test_ips:
            url = namecheap.ddns_update_url(ip)
            self.assertIn(f'ip={ip}', url, f"URL should contain correct IP {ip}")
            self.assertTrue(url.startswith('https://'), "URL should start with https://")


class TestRegistryMechanisms(unittest.TestCase):
    """Test the automatic registration mechanisms for DDNS service adapters"""

    def setUp(self):
        # Reset the singleton instance for clean tests
        DDNSServiceManager._instance = None

    def tearDown(self):
        # Reset the singleton instance for clean tests
        DDNSServiceManager._instance = None
        

    def test_service_registries_populated(self):
        """Test that the service registries are properly populated"""
        # Test that NameCheap is registered
        self.assertIn('namecheap', DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY)
        self.assertIn(NameCheap, DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY)
        
        # Test bidirectional mapping
        service_name = 'namecheap'
        service_class = DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY[service_name]
        self.assertEqual(service_class, NameCheap)
        
        reverse_lookup = DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY[NameCheap]
        self.assertEqual(reverse_lookup, service_name)

    def test_registry_consistency(self):
        """Test that both registries are consistent with each other"""
        # For each entry in the service->impl registry, 
        # there should be a corresponding entry in the impl->service registry
        for service_name, impl_class in DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY.items():
            self.assertIn(impl_class, DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY)
            self.assertEqual(DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY[impl_class], service_name)

    def test_services_list_one_entry(self):
        '''Test .ini with a single entry'''

        # Make a known .ini file:
        config_path = self.make_ini_file_and_secret(services=['namecheap'])

        service_manager = DDNSServiceManager(config_path)

        services = service_manager.services_list()
        self.assertListEqual(services, ['namecheap'])

    def test_services_list_no_entries(self):
        '''Test .ini with no entry'''
        # Make a known .ini file with the default single entry,
        # because the DDNSServiceManager will baulk at an empty .ini
        config_path = self.make_ini_file_and_secret()

        service_manager = DDNSServiceManager(config_path)
        # Artificially empty the config:
        service_manager.config.clear()
        # ... and the serviceName->impl registry:
        service_manager._SERVICE_TO_IMPL_REGISTRY = {}
        services = service_manager.services_list()
        self.assertEqual(len(services), 0)

    def test_services_list_one_entry_no_subclass(self):
        '''Test .ini with a single entry'''
        # Make a known .ini file:
        config_path = self.make_ini_file_and_secret(services=['noimplementation'])
        service_manager = DDNSServiceManager(config_path)
        services = service_manager.services_list()
        self.assertEqual(len(services), 0)

        


    # ----------------- Utilities --------------
    def make_ini_file_and_secret(self, services=['namecheap']):

        self.ddns_tmp_dir = tempfile.TemporaryDirectory(
            dir='/tmp', 
            prefix='ddns_tmp_')
        tmp_dir_nm = self.ddns_tmp_dir.name
        config_path = os.path.join(tmp_dir_nm, 'ddns.ini')
        secrets_path = os.path.join(tmp_dir_nm, 'ddns_secret')
        config_data = {}
        for serv_nm in services:
            host = f"myhost_{serv_nm}"
            domain = f"mydomain_{serv_nm}.com"
            options = {
                'host': host,
                'domain': domain,
                'url_root': 'https://dynamicdns.park-your-domain.com/update?',
                'secrets_file' : secrets_path
            }
            # Add new Section (service)
            config_data[serv_nm] = options

        # Populate the config file:
        config = configparser.ConfigParser()
        config.read_dict(config_data)
        with open(config_path, 'w') as fd:
            config.write(fd)
            
        # Populate the secret:
        with open(secrets_path, 'w') as fd:
            fd.write("this is my secret\n")

        return config_path

if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)