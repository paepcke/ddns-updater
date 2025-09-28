# **********************************************************
#
# @Author: Andreas Paepcke
# @Date:   2025-09-27 17:22:28
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/test/test_dns_service.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-27 17:28:25
#
# **********************************************************

import unittest

from lanmanagement.dns_service import DNSService

class TestDNSService(unittest.TestCase):
    
    def setUp(self):
        pass

    #----------- Tests ------------

    def test_get_a_records_from_server(self):

        host = 'dresl.net'
        nameserver = 'dns1.registrar-servers.com'
        ip_addrs = DNSService.get_a_records_from_server(host, nameserver)
        print(ip_addrs)

# ------------------------ Main ------------
if __name__ == '__main__':
    unittest.main(verbosity=2)