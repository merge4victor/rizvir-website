
### Get a list of all Load Balancer (=EC2 service) IP ranges for a region:

This uses the AWS [ip-ranges](https://ip-ranges.amazonaws.com/ip-ranges.json) file to output all the current IP ranges used by a service in a region. You need to install jq for this to work:

```bash
service=EC2
region=ap-southeast-2
curl -s https://ip-ranges.amazonaws.com/ip-ranges.json |  jq ".prefixes | .[] | select(.service==\"$service\") | select(.region==\"$region\") | .ip_prefix" | tr -d '"'
```


### Using MFA with the AWS CLI, when using cross account role switching

It's a good idea to mandate MFA. 

Ideally, you would have an AWS account whose only purpose is have your IAM users, and you would from there role switch to another AWS account. Setting that up with AWS is simple, first add the AWS profile of the main account to your **~/.aws/config** file:

```ini
[profile main-account]
output = json
region = ap-southeast-2
```

And  **~/.aws/credentials**:
```ini
[main-account]
aws_access_key_id = ABCD1243435875324534
aws_secret_access_key = abcd1234328434434234235094385
```

Then get the ARN of your MFA token configured in IAM, and also get the ARN of the Role kept in the account you want to access, and use it to create a config:
```ini
[profile my-dev-account]
output = json
region = ap-southeast-2
role_arn = arn:aws:iam::2223456788:role/MyAdminRole
mfa_serial = arn:aws:iam::111234567:mfa/my.main.account.iam.username
source_profile = main-account
```

### Using MFA with the AWS CLI, when using cross account role switching with temporary keys

The above method (using the mfa_serial & role_arn in the config) works well, but may not properly support certain applications that use something like boto. For example, with Ansible, once you point your AWS_PROFILE to use the MFA enabled account, it will ask for the MFA token with every task that uses AWS, which quickly gets annoying, especially as one cannot use the same MFA token twice, thus resulting in you having to wait for 30 seconds before it goes to the next Ansible tasks. Packer gets wonky with MFA too.

What you can do instead is have a script to save the temporary credentials into a named profile. This way, applications do not need to specifically handle MFA, and can just use a normal non-MFA AWS named profile. To do this, create the main account credentials like in the previous step:

```ini
# ~/.aws/config
[profile main-account]
output = json
region = ap-southeast-2
```

```ini
# ~/.aws/credentials
[main-account]
aws_access_key_id = ABCD1243435875324534
aws_secret_access_key = abcd1234328434434234235094385
```

Then create a placeholder for the prod account in your config:

```ini
# ~/.aws/config
[profile prod-account]
output = json
region = ap-southeast-2
```

And then save this script somewhere:

```bash
# This script modifies the ~/.aws/credentials file with temporary credentials
# Take a backup of that file before running this script

MFA_ARN="arn:aws:iam::123456789:mfa/your.iam.user"
ROLE_ARN="arn:aws:iam::4555555555:role/YourAdminRole"
MAIN_PROFILE="main-account"
FINAL_PROFILE="prod-account" # do NOT use an existing profile name, it will overwrite the credentials
sed="sed" # replace with sed=gsed on a Mac, after doing a brew install gnu-sed

SECONDS="3550"
AWS_CREDENTIALS=~/.aws/credentials

mfa_token=""
while [[ ! "${mfa_token}" =~ ^[0-9]{6}$ ]]; do
    read -p "Enter the MFA token: " -n 6 mfa_token
    echo ""
done

set -e
set -u

sts=( $(
    aws --profile $MAIN_PROFILE sts assume-role \
    --role-arn "$ROLE_ARN" \
    --role-session-name "bash-`date +%Y%m%d`" \
    --serial-number $MFA_ARN \
    --token-code $mfa_token \
    --duration-seconds $SECONDS \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text
) )

AWS_ACCESS_KEY_ID=${sts[0]}
AWS_SECRET_ACCESS_KEY=${sts[1]}
AWS_SESSION_TOKEN=${sts[2]} ${@:2}

# Remove all mentions of [ $FINAL_PROFILE ] in the credentials, 3 lines:
$sed -i -e "/\[${FINAL_PROFILE}\]/,+3 d" $AWS_CREDENTIALS

# Then append to it
echo "[${FINAL_PROFILE}]
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_session_token = ${AWS_SESSION_TOKEN}" >> $AWS_CREDENTIALS

echo "You can now use \"aws --profile $FINAL_PROFILE ...\" for $SECONDS seconds"
```

Then run the script, enter your MFA token, and test it by typing:
```
aws --profile prod-account s3 ls
# or
export AWS_PROFILE=prod-account
aws s3 ls
```


### Asking for the AWS MFA token for cross account roles within Ansible

Ansible does not work well with MFA enabled profiles; it would ask for the MFA token at every task which quickly gets annoying, particularly since you cannot reuse the same MFA token and have to wait 30 seconds between each task.

To solve this, consider using the previous approach ("Using MFA with the AWS CLI, when using cross account role switching with temporary keys"). However, if most of your team already set up their AWS CLI for MFA enabled cross account role switching using the standard approach documented in "Using MFA with the AWS CLI, when using cross account role switching", it is possible for Ansible to read the information in your aws config files and ask for the MFA token once per playbook-run. 

This is an example of such a setup:

```yaml
- hosts: localhost
  vars:
	region: ap-southeast-2
    aws_profile: your-dev-account
  connection: local
  gather_facts: no
  vars_prompt:
    - name: "mfa_token"
      prompt: "Enter the MFA token"
  environment:
    AWS_REGION: "{{ region }}"
  tasks:
    - set_fact:
        aws_profile: "{{ aws_profile }}"

    - sts_assume_role:
        mfa_token: "{{ mfa_token }}"
        mfa_serial_number: "{{ lookup('ini', 'mfa_serial section=profile {{aws_profile}} file=~/.aws/config') }}"
        role_arn: "{{ lookup('ini', 'role_arn section=profile {{aws_profile}} file=~/.aws/config') }}"
        aws_access_key:  "{{ lookup('ini', 'aws_access_key_id section={{source_profile}} file=~/.aws/credentials') }}"
        aws_secret_key:  "{{ lookup('ini', 'aws_secret_access_key section={{source_profile}} file=~/.aws/credentials') }}"
        role_session_name: "ansible"
      vars:
        source_profile: "{{ lookup('ini', 'source_profile section=profile {{aws_profile}} file=~/.aws/config') }}"
      register: role_env

	# START aws block:
	- block:
		- aws_s3_bucket_facts:
 	      register: buckets
	
		- debug:
			msg: "{{ buckets }}"

      environment:
            AWS_SECRET_ACCESS_KEY: "{{ role_env.sts_creds.secret_key }}"
            AWS_ACCESS_KEY_ID: "{{ role_env.sts_creds.access_key }}"
            AWS_SESSION_TOKEN: "{{ role_env.sts_creds.session_token }}"
	# END aws block.
```		





### Using MFA with the AWS CLI, within the same account

If you don't have multiple AWS accounts and want to use MFA with your access keys (and had a restriction in your IAM user to mandate MFA), it's a bit harder to configure. You essentially have to follow this:

[https://aws.amazon.com/premiumsupport/knowledge-center/authenticate-mfa-cli/](https://aws.amazon.com/premiumsupport/knowledge-center/authenticate-mfa-cli/)

You can either follow the steps in that amazon link, or use this script. The script needs GNU sed; on a mac you would need:

```
brew install gnu-sed
```

First have this in your ~/.aws/config:
```ini
[profile your-account-no-mfa]
output = json
region = ap-southeast-2

[profile your-account]
output = json
region = ap-southeast-2
```

Then put in your ~/.aws/credentials for the no-mfa bit:

```
[your-account-no-mfa]
aws_access_key_id = ABCDEF12345677
aws_secret_access_key = abcd243908349abcd79872342434
```

Then use this script to ask for your MFA and modify your aws credentials file (take a backup of your AWS credential file); store it anywhere:

```bash
# This script modifies the ~/.aws/credentials file with temporary credentials
# Take a backup of that file before running this script

MFA_ARN="arn:aws:iam::012345678:mfa/your.username"
MAIN_PROFILE="your-account-no-mfa"
FINAL_PROFILE="your-account"
sed="gsed" # replace with sed=sed in Linux

SECONDS="86400"
AWS_CREDENTIALS=~/.aws/credentials

mfa_token=""
while [[ ! "${mfa_token}" =~ ^[0-9]{6}$ ]]; do
    read -p "Enter the MFA token: " -n 6 mfa_token
    echo ""
done

set -e
set -u

sts=( $(
    aws --profile $MAIN_PROFILE sts get-session-token \
    --serial-number $MFA_ARN \
    --token-code $mfa_token \
    --duration-seconds $SECONDS \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
    --output text
) )

AWS_ACCESS_KEY_ID=${sts[0]}
AWS_SECRET_ACCESS_KEY=${sts[1]}
AWS_SESSION_TOKEN=${sts[2]} ${@:2}

# Remove all mentions of [ $FINAL_PROFILE ] in the credentials, 3 lines:
$sed -i -e "/\[${FINAL_PROFILE}\]/,+3 d" $AWS_CREDENTIALS

# Then append to it
echo "[${FINAL_PROFILE}]
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_session_token = ${AWS_SESSION_TOKEN}" >> $AWS_CREDENTIALS

echo "You can now use \"aws --profile $FINAL_PROFILE ...\" for $SECONDS seconds"
```

Then run the script, enter your MFA token, and test it by typing:
```
aws --profile your-account s3 ls
```




### Assume cross account role in a BASH script

This assumes the role $role_arn on the current shell, assuming the IAM instance profile has permissions to assume that role ARN:

```bash

    role_arn="..."

    sts=( $(
        aws sts assume-role \
        --role-arn "$role_arn" \
        --role-session-name "roleswitch-`date +%Y%m%d`" \
        --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
        --output text
    ) )
    export AWS_ACCESS_KEY_ID=${sts[0]}
    export AWS_SECRET_ACCESS_KEY=${sts[1]}
    export AWS_SESSION_TOKEN=${sts[2]} ${@:2}
```



### Assume role in a Jenkins Pipeline stage

You can use this if you want to assume an AWS role in one of the Jenkinsfile stages, and have that available in all other stages. The issue is that Jenkins does not pass exported environment variables from one stage into another, so we need to use a workaround that writes the variables into a file, and then uses some groovy to inject those variables as environment variables available for the rest of the stages:


```
    environment {
        region = "ap-southeast-2"
        aws_role = "arn:aws:iam::1234567889:role/YourRole"
    }

    ...

        stage('Assume AWS role') {
            steps {
                sh '''#!/bin/bash -eu
                    sts=( $(
                        aws sts assume-role \
                        --role-arn "$aws_role" \
                        --role-session-name "jenkins-`date +%Y%m%d`" \
                        --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
                        --output text
                    ) )
                    echo -n ${sts[0]} > .AWS_ACCESS_KEY_ID
                    echo -n ${sts[1]} > .AWS_SECRET_ACCESS_KEY
                    echo -n ${sts[2]} > .AWS_SESSION_TOKEN
                '''
                script {
                    env.AWS_ACCESS_KEY_ID = readFile('.AWS_ACCESS_KEY_ID')
                    env.AWS_SECRET_ACCESS_KEY = readFile('.AWS_SECRET_ACCESS_KEY')
                    env.AWS_SESSION_TOKEN = readFile('.AWS_SESSION_TOKEN')
                    env.AWS_DEFAULT_REGION = env.region
                }

            }
        }

        stage('Your second stage') {
            steps {
                sh '''
                    aws ec2 describe-instances
                '''
            }
        }
```


### Using the latest CentOS 7 image in Packer

```json
    ...
    "source_ami_filter": {
        "filters": {
            "name": "*CentOS Linux 7*",
            "owner-alias": "aws-marketplace",
            "virtualization-type": "hvm",
            "architecture": "x86_64",
            "root-device-type": "ebs"
        },
        "most_recent": true
      },
```




### Example script to apply CloudFormation updates

Everyone tends to have different ways of managing CloudFormation templates, and associated scripts to apply them. This is a quick one I use; and the bit you may want to steal is verifying the status of the update at the end (instead of having to visit the CloudFormation console).

This assumes you have files like loadbalancer.yml, and it's parameters in a file like say "loadbalancer.params.json" with the list of parameters and values, like:
```json
    [
      { "ParameterKey": "Environment", "ParameterValue": "dev" },
      { "ParameterKey": "SomeOtherParameter", "ParameterValue": "somevalue" }
    ]
```

If you don't have any parameters, just put in `[]` in your parameters file.

Then you can run the following script like:
```
export AWS_PROFILE="your_aws_cli_profile"
./cfn.sh create|update|change stack_name template_file.yml parameter_file.json
```

It'd wait until the stack is created successfully or rolls back:

```
./cfn.sh create MyApplication application.yml application.params.dev.json
...
Sun Feb 25 11:41:40 AEDT 2018 : Current status is CREATE_IN_PROGRESS, waiting for CREATE_COMPLETE (try 24 of 300)
Sun Feb 25 11:41:45 AEDT 2018 : Current status is CREATE_IN_PROGRESS, waiting for CREATE_COMPLETE (try 25 of 300)
Sun Feb 25 11:41:51 AEDT 2018 : Current status is CREATE_IN_PROGRESS, waiting for CREATE_COMPLETE (try 26 of 300)
Sun Feb 25 11:41:56 AEDT 2018 : Current status is CREATE_COMPLETE, waiting for CREATE_COMPLETE (try 27 of 300)
Got status CREATE_COMPLETE
```

This is the script:

```bash
#!/bin/bash

# Customize location or parameters of the aws command if needed:
aws="aws"

# If it's not an EC2 instance:
if [[ ! -f /sys/hypervisor/uuid && `head -c 3 /sys/hypervisor/uuid > /dev/null 2>&1 ` != ec2 ]]; then
    #and the AWS_PROFILE was not defined
    if [[ "$AWS_PROFILE" == "" ]]; then
        echo "No AWS_PROFILE defined, type:"
        echo "export AWS_PROFILE='your_aws_profile_name'"
        exit 1
    fi
fi

set -e
set -u

if [ $# == 0 ]; then
    echo "Usage: ./cfn.sh create|update|change stack_name template_file.yml parameter_file.json"
    exit 1
fi

action="${1:?1st argument is either update or create}"
stack_name="${2:?2nd argument is stack name}"
template_file="${3:?3rd argument is the template file path}"
parameters_file="${4:?4th argument is the parameter JSON file}"


# Validate template:
$aws cloudformation validate-template --template-body file:///`pwd`/$template_file
if [ $? != 0 ]; then
    echo "Validation failed, aborting."
    exit 1
fi
echo "Validation successful"

if [[ "$action" == "change" ]]; then
    $aws cloudformation create-change-set --stack-name $stack_name --template-body file:///`pwd`//$template_file --parameters "$(cat $parameters_file)" --capabilities CAPABILITY_NAMED_IAM --change-set-name "CliUpdate-$(date +%Y%m%d%H%M%S)"
else
    # Apply template
    $aws cloudformation $action-stack --stack-name $stack_name --template-body file:///`pwd`//$template_file --parameters "$(cat $parameters_file)" --capabilities CAPABILITY_NAMED_IAM
fi


# Get stack status:
function get_cfn_status() {
    local stack_name=$1
    $aws --output text cloudformation describe-stacks --stack-name $stack_name --query Stacks[].StackStatus
}


# Waits until the stack is in the given status
# eg. wait_until_cfn_status stack_name UPDATE_COMPLETE
function wait_until_cfn_status() {
    local stack_name=$1
    local status_needed=$2

    current_status=""
    max_tries=300
    seconds_between_tries=5
    tries=0
    while [ "$current_status" != "$status_needed" ]; do
        current_status=$(get_cfn_status $stack_name)
        echo "`date` : Current status is $current_status, waiting for $status_needed (try $tries of $max_tries)"
        tries=$((tries+1))
        sleep $seconds_between_tries
        if [ "$tries" -gt "$max_tries" ]; then
            echo "Max timeout reached"
            return 1
        elif [[ "$current_status" =~ .*ROLLBACK.* || "$current_status" =~ .*FAILED.* ]]; then
            echo "Apply failed, status is $current_status"
			aws cloudformation describe-stack-events --stack-name $stack_name --output text | head -n5
            return 1
        fi
    done

    echo "Got status $current_status"
    return 0
}

if [[ "$action" != "change" ]]; then
    # First wait until CloudFormation is in CREATE_IN_PROGRESS or UPDATE_IN_PROGRESS
    action_caps=$(echo $action | tr '[:lower:]' '[:upper:]')
    wait_until_cfn_status $stack_name ${action_caps}_IN_PROGRESS || { echo "Update failed";  exit 1; }
    # Then until it's done:
    wait_until_cfn_status $stack_name ${action_caps}_COMPLETE || { echo "Update failed" ; exit 1; }
fi
```


### Login in your region

If you're not in the US, the AWS management console log in page can sometimes be slow, so say if you're in or near the ap-southeast-2 region, use this URL to log into your AWS account:

https://**account**.signin.aws.amazon.com/console?region=**ap-southeast-2**


