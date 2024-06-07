#!/usr/bin/env python3
# Generate SSH config for AWS EC2 instances
# Usage: python3 app.py --ignore-host-key --region us-east-1 --suffix .example.com --tags Name,Environment --proxy-host bastion.example.com
import json
import boto3
import botocore
import os
import argparse
import sys

# Constants
# Regions to exclude from the list of regions to consider
BLACKLISTED_REGIONS = ['cn-north-1', 'us-gov-west-1']
# AMI names to SSH usernames mapping
AMI_NAMES_TO_USER = {
    'amzn': 'ec2-user',
    'ubuntu': 'ubuntu',
    'CentOS': 'root',
    'DataStax': 'ubuntu',
    'CoreOS': 'core',
    'Debian': 'admin',
    'Fedora': 'fedora',
    'FreeBSD': 'ec2-user'
}
# AMI IDs to SSH usernames mapping
AMI_IDS_TO_USER = {
    'ami-ada2b6c4': 'ubuntu'
}
# AMI IDs to SSH key mapping
AMI_IDS_TO_KEY = {
    'ami-ada2b6c4': 'custom_key'
}

# Argument parsing
parser = argparse.ArgumentParser(description="Generate SSH config for AWS EC2 instances.")
parser.add_argument('--default-user', type=str, default=None,
                    help='Default ssh username to use if it can\'t be detected from AMI name.')
parser.add_argument('--exclude-filter', type=str, default='',
                    help=argparse.SUPPRESS) # Still WIP
parser.add_argument('--filter', type=str, default='{"instance-state-name": "running"}',
                    help='JSON string of filters to apply when querying EC2 instances. Default: \'{"instance-state-name": "running"}\'')
parser.add_argument("--ignore-host-key", action="store_true",
                    help="Ignore SSH host key checking.")
parser.add_argument('--prefix', default='', type=str,
                    help='Specify a prefix to prepend to all host names. Default: ""')
parser.add_argument('--profile', type=str,
                    help='Specify AWS credential profile to use. If not set, default credentials are used.')
parser.add_argument("--proxy-host", type=str, default=None,
                    help="Specify proxy host for SSH connections. Used for connecting to instances via a bastion host.")
parser.add_argument("--region", type=str, default=None,
                    help="Specify AWS region. If set, all calls to AWS API are made on this region only.")
parser.add_argument('--ssh-key-dir', type=str, default='~/.ssh/',
                    help='Location of private keys. Default: ~/.ssh/')
parser.add_argument('--ssh-key-name', default='', type=str,
                    help='Override the ssh key to use for all hosts. If not set, the key name is fetched from the instance.')
parser.add_argument('--ssh-key-suffix', default='.pem', type=str, 
                    help='Specify the file extension for the key name received in instance metadata. Default: .pem')
parser.add_argument('--suffix', default='', type=str,
                    help='Specify a suffix to append to all host names.')
parser.add_argument('--tags', type=str, default=None,
                    help='A comma-separated list of tag names to be considered for concatenation in the Host. Not providing this will name instances by their instanceId.')
parser.add_argument("--use-public-ip", action="store_true",
                    help="Use public IP addresses in the SSH config. Defaults to private IP if not set.")
parser.add_argument('--user', type=str, default=None,
                    help='Override the ssh username for all hosts')
parser.add_argument('--white-list-region', default='', nargs='+', 
                    help='Which regions must be included. If omitted, all regions are considered')

args = parser.parse_args()

# Get the default region from environment variable or set it to 'us-east-1'
default_region = args.region if args.region else os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

# Setup AWS profile if specified
session = boto3.Session(profile_name=args.profile, region_name=default_region) if args.profile else boto3.Session(region_name=default_region)

# Determine regions to operate on
if args.region:
    # Use the specified region (even if it's blacklisted)
    regions = [args.region]
elif args.white_list_region:
    # Filter out blacklisted regions
    regions = [region for region in args.white_list_region if region not in BLACKLISTED_REGIONS]
else:
    # Get all regions except the blacklisted ones
    ec2 = session.client('ec2')
    response = ec2.describe_regions()
    regions = [region['RegionName'] for region in response['Regions'] if region['RegionName'] not in BLACKLISTED_REGIONS]

# Convert the filters from a JSON string to a dictionary
try:
    custom_filters = json.loads(args.filter)
except json.JSONDecodeError:
    print("Failed to parse filters. Ensure it is a valid JSON string.")
    sys.exit(1)
try:
    exclude_filters = json.loads(args.exclude_filter) if args.exclude_filter else {}
except json.JSONDecodeError:
    print("Failed to parse exclude filters. Ensure it is a valid JSON string.")
    sys.exit(1)

# Function to check if instance should be excluded based on exclude_filters
def should_exclude(instance):
    for key, value in exclude_filters.items():
        if key.startswith('tag:'):
            # Extract tag name and check against instance tags
            tag_name = key.split(':', 1)[1]
            if any(tag['Key'] == tag_name and value.lower() in tag['Value'].lower() for tag in instance.get('Tags', [])):
                return True
        else:
            # Directly check the instance attributes
            if str(instance.get(key, '')).lower() == value.lower():
                return True
    return False

# Function to determine the SSH username based on AMI ID
def get_username(ami_id, region):
    try:
        client = session.client('ec2', region_name=region)
        response = client.describe_images(ImageIds=[ami_id])
        # Extract the AMI name from the response
        if not response['Images']:
            #print("# Response: " + str(response))
            raise ValueError(f"No AMI found with ID {ami_id}")
        ami_name = response['Images'][0]['Name'].lower()

        for keyword, username in AMI_NAMES_TO_USER.items():
            if keyword.lower() in ami_name:
                print(f"# AMI {ami_name} matched with [{keyword}] for user: {username}")
                return username
        #return AMI_IDS_TO_USER.get(ami_id, "ec2-user")  # Default to 'ec2-user' if no specific match
        return AMI_IDS_TO_USER.get(ami_id, args.default_user if args.default_user else "ec2-user") 
    except (boto3.exceptions.Boto3Error, botocore.exceptions.ClientError, ValueError) as e:
        print(f"# Error retrieving AMI details for AMI ID {ami_id}: {e}")
        return "ec2-user"  # Fallback to a default user if there's an error

# Initialize a dictionary to keep track of hostname occurrences and a list to hold instance data
hostname_counts = {}
instance_data = []

# Main logic to generate SSH config entries
for region in regions:
    client = session.client('ec2', region_name=region)
    # instances_response = client.describe_instances(
    #     Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
    # )
    instances_response = client.describe_instances(
        Filters=[{'Name': key, 'Values': [value]} 
                 for key, value in custom_filters.items()])
    # collect all instances from all reservations
    all_instances = [
        instance
        for reservation in instances_response['Reservations']
        for instance in reservation['Instances']
    ]

    # Filter out instances based on exclude_filters
    if args.exclude_filter:
        filtered_instances = [instance 
                            for instance in all_instances 
                            if not should_exclude(instance)]
        all_instances = filtered_instances
    
    for instance in all_instances:
        # Initialize the ip_address variable to None
        ip_address = None

        if args.use_public_ip:
            # Try to use the public IP address if available
            if 'PublicIpAddress' in instance:
                ip_address = instance['PublicIpAddress']
            elif 'PrivateIpAddress' in instance:
                # Fallback to private IP if public IP is not available
                ip_address = instance['PrivateIpAddress']
            else:
                # If neither IP is available, log an error and skip this instance
                sys.stderr.write(f"Cannot lookup IP address for instance {instance['InstanceId']}, skipped it.\n")
                continue
        else:
            # Use the private IP address if available
            if 'PrivateIpAddress' in instance:
                ip_address = instance['PrivateIpAddress']
            else:
                # Log an error and skip this instance if no private IP is available
                sys.stderr.write(f"Cannot lookup private IP address for instance {instance['InstanceId']}, skipped it.\n")
                continue

        # Fetch and concatenate specified tags if any
        tag_string = ''
        base_hostname = ''

        if args.tags:
            specified_tags = args.tags.split(',')
            # Construct a dictionary of tags where both key and value are available and value is not empty
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] in specified_tags and tag['Value']}
            # Collect values for the specified tags, ignoring empty strings
            tag_values = [tags[tag] for tag in specified_tags if tag in tags and tags[tag].strip()]
            tag_string = '-'.join(tag_values)
            # Determine the hostname to use, fallback to instanceId if no tags are available
            if tag_string:
                base_hostname = f"{args.prefix}{tag_string}".strip()
            else:
                base_hostname = f"{args.prefix}{instance['InstanceId']}".strip()
        else:
            # If no tags are specified, use the instanceId as the hostname
            base_hostname = f"{args.prefix}{instance['InstanceId']}".strip()

        # Increment the count of occurrences of the base hostname
        hostname_counts[base_hostname] = hostname_counts.get(base_hostname, 0) + 1
        
        # Store instance information to process later
        instance_data.append({
            'base_hostname': base_hostname,
            'ip_address': ip_address,
            'instance_id': instance['InstanceId'],
            'ami_id': instance['ImageId'],
            'keyname': instance['KeyName'].replace(' ', '_')
        })
        #print(f"# {instance['InstanceId']} - {base_hostname} - {ip_address}")


# Print the collected data for debugging
# print("# Collected instance data:")
# for data in instance_data:
#     print(f"# {data}")
# print("# Hostname counts:")
# for hostname, count in hostname_counts.items():
#     print(f"# {hostname}: {count}")

# Initialize a dictionary to keep track of output hostname occurrences
output_counts = {}

# Process and print the SSH config entries
for data in instance_data:
    base_hostname = data['base_hostname']
    count = hostname_counts[base_hostname]
    if base_hostname not in output_counts:
        output_counts[base_hostname] = 0
    output_counts[base_hostname] += 1
    if count > 1:
        #print(f"# Repeated occurrence of hostname {base_hostname} {count} times")
        hostname = f"{base_hostname}-{output_counts[base_hostname]}{args.suffix}"
    else:
        #print(f"# Just one occurrence of hostname {base_hostname}")
        hostname = f"{base_hostname}{args.suffix}"
    
    ip_address = data['ip_address']
    ami_id = data['ami_id']
    user = args.user or get_username(ami_id, region)
    key_name = args.ssh_key_name or f"{data['keyname']}.{args.ssh_key_suffix}"
    identity_file = os.path.expanduser(os.path.join(args.ssh_key_dir, key_name))

    print(f"# {data['instance_id']}")
    print(f"Host {hostname}")
    print(f"  Hostname {ip_address}")
    print(f"  User {user}")
    print(f"  IdentityFile {identity_file}")
    if args.ignore_host_key:
        print("  StrictHostKeyChecking no")
        print("  UserKnownHostsFile /dev/null")
    if args.proxy_host:
        #print(f"  ProxyCommand ssh -W %h:%p {args.proxy_host}")
        print(f"  ProxyJump {args.proxy_host}")
    print()
