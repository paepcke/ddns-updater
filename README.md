# Extensible DDNS Updater

Pushes the possibly changing IP address of a host myhost.mydomain.com to a remote dynamic domain name service (DDNS).

## Overview
Usage: a cron job would typically be used at regular intervals to run

`sudo /path/to/ddns-updater <ddns-service-name>`

Assuming the program runs on myhost.mydomain.com, it each time:

1. Detects myhost's current IP address
2. Inquires which IP DNS services currently provide for the host
3. If the two IP addresses differ, updates the DDNS service

A rotating log is maintained at

`<package-root>/lanmanagement/logs/ddns.log<n>`

## Installation

Install the package (recommended into a virtual env, like conda):

`pip install ddns-updater-ext`

the program will now be available as `ddns-updater`. Out of the box, NameCheap's DDNS service is supported. See [Extending for New DDNS Services ](#extending-for-new-ddns-services) for how to add others.

DDNS services require some kind of secret, such as a password, or API key. You should place that information for your service in a place like:

`$HOME/.ssh/ddns_password`

where `.ssh` is accessible only for your user (`chmod 700 $HOME/.ssh`). You tell ddns-updater where that secrets file resides in a configuration file `ddns.ini`. You find this configuration file by running

`ddns-updater --info`

This command tells you the location of the default config file, as well as the default location of the secrets file. You can copy that default config file, or change it in place. If you copy it, you then always tell ddns-updater about the new location:

`ddns-updater --config_path path/to/your/ddns.ini <service name>`

Copying that config file, and changing the copy is recommended so that your changes are not overwritten if you update the ddns-updater-ext package.

## Usages

You can immediatly try three commands:

```
ddns-updater --help
ddns-updater --list   # Implemented DDNS services; extensible.
ddns-updater --info   # Location of future logs, the config file,
                      # and the secrets file
```

To run in a terminal: since the active-ingredient command needs to run as `sudo` you need to provide the sudo environment with the full location of `ddns-updater`. This is required because your path is not passed into the sudo environment. You can provide the full path in several ways, either by explicitly typing out the full path, or via:

`sudo `which ddns-updater` namecheap`

Unless an error, such as a misconfiguration occurs, the ddns-updater command runs silently. But you can always check what happened by inspecting the logs (location via `ddns-updater --info`).

You will eventually have the updater run periodically on its own. One method is a `cron` job.

```
# Open an editor with the current root crontab:
sudo crontab -e
# Add a line like this:
0 * * * * /path/to/ddns-updater --config_path /to/ddns.ini namecheap
# Save the file, and check that your change worked:
crontab -l
```
For details, see [crontab(5)](https://man7.org/linux/man-pages/man5/crontab.5.html).

## Implementation

After configuration, the out-of-the-box implementation can interact with NameCheap's DDNS service. The files `utils.py` and `dns_service.py` provide DNS related facilities that can be useful for purposes other than dynamic DNS.

To inspect the code, clone [ddns-updater](https://github.com/paepcke/ddns-updater) into proj-root. Then:

```
cd <proj-root>
pip install .
# You can run the unittests via:
pytest
```

### Extending for New DDNS Services

Administrators can extend the implementation to interact with additional DDNS services. The core of these service interactions is to generate a proper URL that instructs the service to update its IP address for `myhost.mydomain.com/.net.io,...` For each supported service the query parameters are stored as a section of options in a Python `configparser` `ddns.ini` file. Like this:

```ini
[namecheap]

# Part of URL for updating service before the query parms:
url_root     = https://dynamicdns.park-your-domain.com/update?
secrets_file = $HOME/.ssh/ddns_password
# The query parameters:
host         = myhost
domain       = mydomain.net
```

Other services might require additional information.

The administrator creates a short subclass, such as `NameCheap` in `ddns_service_adapters.py`. The class just needs to provide a single method `ddns_update_url(new_ip),` which returns a URL suitable to send to the new DDNS service for IP update.

### Architecture

The main class is `DDNSUpdater`. Its constructor takes a DDNS servicename, such as "namecheap". That name is provided as argument when `ddns_updater.py` is run on the command line, or in a `cron` job.

<div align="center">
  <img src="https://raw.githubusercontent.com/paepcke/ddns-updater/main/readme_architecture.png"
       alt="DDNS service update architecture"
       width="400px"
       >
</div>

The `DDNSUpdater` requests a handler for the respective DDNS service from a singleton instance of class `DDNSServiceManager`. This returned handler will be an instance of the subclass mentioned in [Extending for New DDNS Services ](#extending-for-new-ddns-services). The `DDNSUpdater` then calls `ddns_update_url()` on the handler whenever it determines that the host's IP address has changed. It issues an HTTP request using the returned URL.
