# **********************************************************
#
# @Author: Andreas Paepcke
# @Date:   2025-09-20 18:25:56
# @File:   /Users/paepcke/VSCodeWorkspaces/ddns-updater/src/lanmanagement/ddns_service_adapters.py
# @Last Modified by:   Andreas Paepcke
# @Last Modified time: 2025-09-29 19:22:15
#
# **********************************************************

'''
This module is an abstraciton for the variety of 
DDNS services on the market. The main function is to
provide URLs that are appropriate for updating a
specific service with a new IP. 

At the core is a .ini config file with a separate
section for each DDNS service. Subclasses of the parent
DDNSServiceManager class provide a ddns_update_url()
method that uses the respective config section's option 
values to construct the service update URL.

The manager (parent) class provides information about available
adapters (a.k.a subclasses and sections in the .ini file). It
is also the factory for the adapters---the instances of
subclasses. To obtain an instance on which clients then
call ddns_update_url(), use 
      <manager-inst>.get_service_adapter(service_name)

Usage:
    ddns_service_fact = DDNSSerivceManager(<config-file-path>)
    ddns_adapter = ddns_service_fact(<service-name>)

    ... detect new IP for host.domain ...
    update_url = ddns_adapter.ddns_update_url(<new-ip>)
    ... send update_url to service ...
'''

import configparser
import os
from pathlib import Path
from typing import Type

class DDNSServiceManager:
    '''
    Factory for instances of subclasses, each of which
    implement one DDNS service. This is a singleton class.
    '''

    # Singleton instance
    _instance = None 
    
    # The DDNS service .ini config file; override 
    # via kwarg config_file=<otherPath> during instantiation:
    # of this class:
    DEFAULT_CONFIG_FILE = Path(__file__).parent / 'ddns.ini'

    # Map from DDNS service name to relevant subclass object
    _SERVICE_TO_IMPL_REGISTRY   = {}
    
    # Map from subclass obj that implements a DDNS service 
    # to service name (i.e. the reverse of _SERVICE_TO_IMPL_REGISTRY)
    _IMPL_TO_SERVICE_REGISTRY   = {}

    #------------------------------------
    # __new__
    #-------------------

    def __new__(cls, *args, **kwargs):
        if cls is DDNSServiceManager:
            if not cls._instance:
                # If the instance doesn't exist, create it using the superclass's __new__
                # It will call __init__():
                cls._instance = super().__new__(cls)
            # Hand out the existing instance:
            return cls._instance
        else:
            # For subclasses, create new instances normally
            return super().__new__(cls)
    
    #------------------------------------
    # Constructor
    #-------------------    

    def __init__(self, config_file=None):

        # Only initialize the first time
        if hasattr(self, 'initialized'):
            return
        
        self.initialized = True
        
        if config_file is None:
            config_file = DDNSServiceManager.DEFAULT_CONFIG_FILE

        self.config_file = config_file

        # All subclasses (DDNS service implementations share the config)
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        if len(self.config.sections()) == 0:
            # When file is not found, the read()
            # returns an empty config. We don't 
            # know which other conditions might do
            # that. Try to explain at least the
            # obvious: a bad path:
            if not os.path.exists(config_file):
                msg = f"Config file {config_file} does not exist"
                raise FileNotFoundError(msg)
            else:
                msg = f"Config file {config_file} seems empty; if it is not, syntax problems?"
                raise TypeError(msg)

    #------------------------------------
    # service_name
    #-------------------

    def service_name(self):
        '''
        Return service name. Only meaningful to call on a subclass instance,
        i.e. on a DDNS service instance. 

        Uses the implementation-to-service-name registry to find th name

        :return: service name whose implementation this class provides
        :rtype: str
        :raise TypeError if called on instance of the parent.
        '''

        if self.__class__ == DDNSServiceManager:
            msg = "Can only call service_name on a service adapter instance, not the DDNSServiceManager parent"
            raise TypeError(msg)

        # Just use the lookup table that was updated
        # automatically with the definition of this subclass:
        return DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY[self.__class__]

    #------------------------------------
    # services_list
    #-------------------

    def services_list(self):
        '''
        Returns a list of DDNS service covered in the .ini file.
        Ensures that each entry also has a respective subclass that
        implements the ddns_update_url() method

        :return: a list of DDNS services names
        :rtype: list[str]
        '''
        service_names = set(self.config.sections())
        service_impls = set(DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY.keys())
        available = service_names.intersection(service_impls)
        return list(available)

    #------------------------------------
    # service_options
    #-------------------

    def service_options(self, service_name=None):
        '''
        Intended to be called without argument by subclasses 
        that implement particular services. OK to call directly
        on the parent instance with a service name.

        :param service_name: name of DDNS service
        :type service_name: str
        :return: the config options of just the specified service
        :rtype: dict[str, str]
        '''
        service_name = service_name if service_name is not None else self.service_name()

        # Return just the config section dict that
        # contains the options for the given service:
        return dict(self.config[service_name])

    #------------------------------------
    # __init_subclass__
    #-------------------

    def __init_subclass__(cls, **kwargs):
        '''
        This a 'magic-method'; it is called by Python whenever
        a subclass of this class (DDNSServiceManager) is defined.
        We get the subclass name, and associate it with the subclass
        object
        '''
        super().__init_subclass__(**kwargs)
        # Automatically register new DDNS service adapter
        # class: service-name --> subclass-object:
        DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY[cls.__name__.lower()] = cls
        # and the reverse for convenience: sublass_obj --> service-name
        DDNSServiceManager._IMPL_TO_SERVICE_REGISTRY[cls] = cls.__name__.lower()

    #------------------------------------
    # get_service_adapter
    #-------------------

    def get_service_adapter(self, service_name: str) -> 'Type[DDNSServiceManager]':
        '''
        Returns an object that understands the DDNS service 
        of the given name. That object is guaranteed to have
        at least method ddns_update_url(), but maybe others,
        depending on the service.

        The quotes around the return type hint is required 
        to avoid a 'that class is not yet defined' forward 
        reference error.

        :param service_name: name of DDNS service as defined in config file secion
        :type service_name: str
        :raises NotImplementedError: if service has no entry in config file
        :raises NotImplementedError: if no subclass for the service exists
        :return: an instance of the subclass appropriate for the service
        :rtype: Type[DDNSServiceManager]
        '''

        # Do we have init info for this service?
        if not self.config.has_section(service_name):
            msg = f"Service '{service_name}' has no entry in config file {self.config_file}"
            raise NotImplementedError(msg)
        
        try:
            adapter_cls_obj = DDNSServiceManager._SERVICE_TO_IMPL_REGISTRY[service_name]
            adapter_obj = adapter_cls_obj.__new__(adapter_cls_obj)
            adapter_obj.config = self.config
            return adapter_obj
        except KeyError:
            raise NotImplementedError(f"Service '{service_name}' is not implemented")

    #------------------------------------
    # ddns_update_url
    #-------------------

    def ddns_update_url(self, new_ip: str):
        '''
        Illegal to call this method on the parent class directly.
        Must call on a subclass.

        :param new_ip: new IP to report to DDNS service
        :type new_ip: str
        :raises NotImplementedError: info that parent is inappropriate for this method
        '''
        raise NotImplementedError("The ddns_update_url() method must be called on a subclass")

    #------------------------------------
    # _retrieve_secret
    #-------------------

    def _retrieve_secret(self, service_name):
        '''
        Given a DDNS service name, return its secret
        by reading it from the file specified in the 
        servive's entry in the config file.

        :param service_name: name of service; any upper/lower casing OK
        :type service_name: str
        :raises KeyError: if config file does not provide a 
            'secrets-file' option for the service
        :return: the secret
        :rtype: str
        '''

        # In the config file the sections are all
        # lower case:
        adapter_section = service_name.lower()
        if not self.config.has_option(adapter_section, 'secrets_file'):
            msg = f"No 'secrets_file' entry in section {adapter_section} of config file {self.config_file}"
            raise KeyError(msg)
        secret_path = self.config[adapter_section]['secrets_file']
        # Resolve tilde and env vars:
        secret_path = self.expand_path(secret_path)
        secret: str = ''
        try:
            with open(secret_path, 'r') as fd:
                secret = fd.read().strip()
        except Exception as e:
            raise FileNotFoundError(f"Could not find/open secrets file '{secret_path}'")
        return secret
    
    #------------------------------------
    # expand_path
    #-------------------    

    def expand_path(self, path: str) -> str:
        '''
        Given a path that might involve tilde and/or 
        env vars, return an absolute path

        :param path: path to resolve
        :type path: str
        :return: path with tilde and/or env vars resolved
        :rtype: str
        '''
        env_vars_resolved = os.path.expandvars(path)
        resolved_path = Path(env_vars_resolved).expanduser()
        return str(resolved_path)
    
    #------------------------------------
    # __repr__
    #-------------------

    def __repr__(self):
        repr_str = f"<DDNS Service Manager at {hex(id(self))}>"
        return repr_str

# ------------------------ Class Namecheap -------------------------

class NameCheap(DDNSServiceManager):
    '''Implements interactions with NameCheap DDNS'''

    #------------------------------------
    # __init__
    #-------------------

    def __init__(self):
        msg = ("DDNS adapter classes must be instantiated via "
               "DDNSServiceManager().get_service_adapter(<service-nm>)")
        raise TypeError(msg)

	#------------------------------------
	# ddns_update_url
	#-------------------

    def ddns_update_url(self, new_ip: str) -> str:
        '''
		Build a URL that will update the DDNS record for
		a host/domain with a new IP on NameCheap. The format 
        of this URL the following URL is required:

			url:
				'https://dynamicdns.park-your-domain.com/update?'
				host=<host>&
				domain=<domain>&
				password=<password>&
				ip=<new-ip>

        We obtain the host and domain from the .ini file, i.e.
        from the parent's self.config

        :param new_ip: the new IP for host.domain
        :type new_ip: str
        :raises KeyError: if no 'url_root' option in namecheap section of config
        :raises KeyError: if no 'host' option in namecheap section of config
        :raises KeyError: if no 'domain' option in namecheap section of config
        :raises KeyError: if no 'secrets_file' option in namecheap section of config
        :raises FileNotFoundError: if secrets file not found or inaccessible
        :return: a URL to access for the IP update
        :rtype: str
        '''

        # By convention, adapter class names are the DDNS
        # service name capitalized:
        # service_name = self.__class__.__name__.lower()
        service_name = 'namecheap'
        try:
            url_base = self.config[service_name]['url_root']
        except KeyError:
            raise KeyError(f"Config entry for service {service_name} has not option 'url_root'")
        
        try:
            host = self.config[service_name]['host']
        except KeyError:
            raise KeyError(f"Config entry for service {service_name} has not option 'host'")

        try:
            domain = self.config[service_name]['domain']
        except KeyError:
            raise KeyError(f"Config entry for service {service_name} has not option 'domain'")

        url =  (url_base +
               f"host={host}&" +
               f"domain={domain}&" +
               f"password={self._retrieve_secret(service_name)}&" +
               f"ip={new_ip}")
        return url

    #------------------------------------
    # __repr__
    #-------------------

    def __repr__(self):
        repr_str = f"<DDNS Service {self.service_name()} at {hex(id(self))}>"
        return repr_str
