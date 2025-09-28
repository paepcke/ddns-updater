# **********************************************************
#
# @Author: Andreas Paepcke
# @Date:   2025-09-27 17:22:28
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/test/test_dns_service.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-28 10:37:39
#
# **********************************************************

import unittest
from unittest.mock import MagicMock, patch

from dns.resolver import Answer

from lanmanagement.dns_service import DNSService

class TestDNSService(unittest.TestCase):
    
    def setUp(self):
        pass

    #----------- Tests ------------

    @patch('lanmanagement.dns_service.dns.resolver.Resolver')    
    def test_get_a_records_from_server(self, mock_resolver_class):

        host = 'myhost.net'
        nameserver = 'dns1.registrar-servers.com'

        # Create a mock instance of the mocked Resolver:
        mock_resolver_instance = MagicMock()
        
        # Have the constructor of the mocked Resolver class
        # return a mock_resolver_instance, instead of a 
        # real one:
        mock_resolver_class.return_value = mock_resolver_instance

        # Create mock DNS record objects
        mock_dns_record = MagicMock()
        # The code to be mocked in the code to be tested 
        # inside the get_A_records() method is:
        #    result = resolver.resolve(domain_or_host, 'A')
        #    return [str(rdata) for rdata in result]
        # The resolver.resolve() method returns list 
        # (i.e. 'result') on which __str__() method is 
        # called in the list comprehension. Give the
        # mock_dns_record a __str__() method:
        
        mock_dns_record.__str__ = lambda self: '192.168.1.100'

        # Mock the resolve() method on our mock Resolver class
        # to return a list of mock_dns_records

        mock_resolver_instance.resolve.return_value = [mock_dns_record]

        ip_addrs = DNSService.get_A_records(host, nameserver)
        self.assertListEqual(ip_addrs, ['192.168.1.100'])

# ------------------------ Main ------------
if __name__ == '__main__':
    unittest.main(verbosity=2)