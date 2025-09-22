# DDNS Updater

Synchronizes the possibly changing IP address of 
myhost.mydomain.com with a remote DDNS service.

Administrators provide details of how to update the
different available services in a ddns.ini file in the
lanmanager package source code directory.

Once the .ini file is in place, and contains a section for
a DDNS service to use, a cron job would typically be used
to run 

The main class is DDNSUpdater. 

When the DDNSUpdater class is instantiated, the current outgoing IP
address is obtained from an IP-echoing Web site. The IP address
currently registered on the DDNS service for the host and domain is
compared against the current actual IP. The DDNS service is updated if
needed.

The recommended use is a cron job that runs the script periodically:


