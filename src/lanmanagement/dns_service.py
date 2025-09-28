 # **********************************************************
 #
 # @Author: Andreas Paepcke
 # @Date:   2025-09-27 16:47:25
 # @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/dns_service.py
 # @Last Modified by:   Andreas Paepcke
 # @Last Modified time: 2025-09-28 10:22:00
 #
 # **********************************************************

import socket
import dns.resolver
# import dns.query
# import dns.message

from lanmanagement.utils import Utils

# --------------------- Class DNSService -------------

class DNSService:
    '''
    Provides DNS services, such as finding name
	server(s) for a given domain, or obtaining
	the DNS A record(s) for a host.
    '''
	
	#------------------------------------
	# get_ns_records
	#-------------------	

    @staticmethod
    def get_ns_records(domain, short=True):
        '''
        Get the name servers for the given domain. 
        Equivalent to the OS level dig command:
            dig ns mydomain.net +short

        Example return:
            ['dns1.registrar-servers.com.',
             'dns2.registrar-servers.com.'
             ]

        :param domain: domain to look up, e.g. 'mydomain.net'
        :type domain: str
        :param short: if True, only a list of nameserver strings is
            returned. Else a list of dns.Answer instances is returned;
            default is True
        :type short: bool
        :return: list of nameservers that are cognizant of the domain,
            or a full dns.resolver.Answer instance.
        :rtype: List[str] | dns.resolver.Answer
        '''
        try:
            dns_Answer = dns.resolver.resolve(domain, 'NS')
            if short:
                return [str(rdata) for rdata in dns_Answer]
            else:
                return dns_Answer
        except dns.resolver.NXDOMAIN:
            raise LookupError(f"Domain {domain} not found")
        except dns.resolver.NoAnswer:
            raise LookupError(f"No NS records found for {domain}")
        except dns.resolver.Timeout:
            raise TimeoutError(f"DNS query timed out for {domain}")
        except dns.resolver.LifetimeTimeout:  # Consider adding this
            raise TimeoutError(f"DNS query lifetime exceeded for {domain}")        
        except dns.exception.DNSException as e:
            raise RuntimeError(f"DNS query failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during DNS query: {e}")        
		
	#------------------------------------
	# get_A_records
	#-------------------

    @staticmethod
    def get_A_records(domain_or_host, nameserver, short=True):
        '''
        Given a domain and a nameserver, return an ip
        address. Equivalent to the OS level dig command

           dig a myhost.mydomain.net @dns1.registrar-servers.com +short

        Trap: if you provide just a domain, like mydomain.net, that
              returns a different IP address than myhost.mydomain.net.
              The domain itself has its own A record.

        :param domain_or_host: a domain, like mydomain.org, or
            a host like myhost.mydomain.org
        :type domain_or_host: string
        :param nameserver: either the name of a relevant
            nameserver, like dns1.registrar-servers.com,
            or its IP address
        :type nameserver: str
        :param short: if True, only a list of nameserver strings is
            returned. Else a list of dns.Answer instances is returned;
            default is True
        :type short: bool

        :raises ValueError: if the domain string is malformed
        :raises TypeError: if domain_or_host is a name string,
            which cannot be resolved to an IP address
        :raises ConnectionError: connection refused, etc.
        :raises LookupError: domain record not found
        :raises LookupError: A record not found
        :raises TimeoutError: server took too long
        :raises RuntimeError: DNS query failure
        :raises RuntimeError: catch-all

        :return: list of host or domain IP addresses, or 
            full dns.resolver.Answer instance
        :rtype: List[str] | dns.resolver.Answer
        '''
        if not Utils.check_domain_syntax(domain_or_host):
            raise ValueError(f"The domain argument '{domain_or_host}' does not look like a valid domain")
        try:
            # Resolve nameserver hostname to IP if it's not already an IP
            if Utils.is_valid_ip(nameserver):
                ns_ip = nameserver
            else:
                ns_ip = Utils.resolve_hostname_to_ip(nameserver)
                if ns_ip is None:
                    msg = f"Nameserver must be a resolvable hostname, or an IP address, not {nameserver}"
                    raise TypeError(msg)

            # Create a custom resolver pointing to specific nameserver IP
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [ns_ip]
            
            resolver_Answer_list = resolver.resolve(domain_or_host, 'A')
            if short:
                # Extract and return just the IP addresses:
                return [str(rdata) for rdata in resolver_Answer_list]
            else:
                return resolver_Answer_list

        except socket.gaierror as e:
            raise ConnectionError(f"Could not resolve nameserver {nameserver}: {e}")
        except dns.resolver.NXDOMAIN:
            raise LookupError(f"Domain {domain_or_host} not found")
        except dns.resolver.NoAnswer:
            raise LookupError(f"No A records found for {domain_or_host}")
        except dns.resolver.Timeout:
            raise TimeoutError(f"DNS query timed out for {domain_or_host}")
        except dns.exception.DNSException as e:
            raise RuntimeError(f"DNS query failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error during DNS query: {e}")        
