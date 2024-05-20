# aws-ec2-ssh-config

This tool automates the generation of [ssh_config(5)](https://man7.org/linux/man-pages/man5/ssh_config.5.html) files for OpenSSH [ssh(1)](https://man7.org/linux/man-pages/man1/ssh.1.html) client, with instances sourced from AWS/EC2.

## Features

- Automatically generate SSH config files for EC2 instances.
- Customize hostnames based on user-specified instance tags, prefixes and suffixes.
- Supports custom SSH key directories and keyfiles, or proxy jump host.

## Prerequisites

- Python 3.6 or higher

## Installation

Clone the repository and install any necessary dependencies:

```sh
git clone https://github.com/gadamo/aws-ec2-ssh-config.git
./aws-ec2-ssh-config/run.sh --help
```

Above commands will download the script, configure a virtual environment with required dependencies, and run it to display usage information:

```
usage: generate_ssh_config.py [-h] [--default-user DEFAULT_USER] [--filter FILTER] [--ignore-host-key] [--prefix PREFIX] [--profile PROFILE]
                              [--proxy-host PROXY_HOST] [--region REGION] [--ssh-key-dir SSH_KEY_DIR] [--ssh-key-name SSH_KEY_NAME]
                              [--ssh-key-suffix SSH_KEY_SUFFIX] [--suffix SUFFIX] [--tags TAGS] [--use-public-ip] [--user USER]
                              [--white-list-region WHITE_LIST_REGION [WHITE_LIST_REGION ...]]

Generate SSH config for AWS EC2 instances.

options:
  -h, --help            show this help message and exit
  --default-user DEFAULT_USER
                        Default ssh username to use if it can't be detected from AMI name.
  --filter FILTER       JSON string of filters to apply when querying EC2 instances. Default: '{"instance-state-name": "running"}'
  --ignore-host-key     Ignore SSH host key checking.
  --prefix PREFIX       Specify a prefix to prepend to all host names. Default: ""
  --profile PROFILE     Specify AWS credential profile to use. If not set, default credentials are used.
  --proxy-host PROXY_HOST
                        Specify proxy host for SSH connections. Used for connecting to instances via a bastion host.
  --region REGION       Specify AWS region. If set, all calls to AWS API are made on this region only.
  --ssh-key-dir SSH_KEY_DIR
                        Location of private keys. Default: ~/.ssh/
  --ssh-key-name SSH_KEY_NAME
                        Override the ssh key to use for all hosts. If not set, the key name is fetched from the instance.
  --ssh-key-suffix SSH_KEY_SUFFIX
                        Specify the file extension for the key name received in instance metadata. Default: .pem
  --suffix SUFFIX       Specify a suffix to append to all host names.
  --tags TAGS           A comma-separated list of tag names to be considered for concatenation in the Host. Not providing this will name instances by
                        their instanceId.
  --use-public-ip       Use public IP addresses in the SSH config. Defaults to private IP if not set.
  --user USER           Override the ssh username for all hosts
  --white-list-region WHITE_LIST_REGION [WHITE_LIST_REGION ...]
                        Which regions must be included. If omitted, all regions are considered
```

### Example Usage

Create a directory and configure ssh client to include config files:

```sh
if [ ! -d ~/.ssh/config.d ]; then
    mkdir ~/.ssh/config.d
    echo 'Include config.d/*' >> ~/.ssh/config
fi
```

Generate config files for connecting to ec2 hosts in your various AWS accounts, e.g:

```sh
export AWS_PROFILE="myprofile"
aws-ec2-ssh-config/run.sh --tags Name,Environment > ~/.ssh/config.d/example-com
export AWS_PROFILE="acmecorp"
aws-ec2-ssh-config/run.sh --prefix "acmesrv-prd-" --tags Name --region us-east-1 > ~/.ssh/config.d/acmecorp-virginia
aws-ec2-ssh-config/run.sh --prefix "acmesrv-drs-" --tags Name --region eu-west-1 > ~/.ssh/config.d/acmecorp-ireland
export AWS_PROFILE="john"
aws-ec2-ssh-config/run.sh --tags Name --region eu-central-1 --filter '{"tag:Name" : "bastion"}' --use-public-ip > ~/.ssh/config.d/bastion-net
aws-ec2-ssh-config/run.sh --tags Name --region eu-central-1 --exclude-filter '{"tag:Name" : "bastion"}' --proxy-host bastion | tee -a ~/.ssh/config.d/bastion-net >/dev/null
## etc.
```
