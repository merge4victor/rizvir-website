This is not a tutorial (read the [CloudFormation::Init](http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-init.html) documentation first); it's just how you can modify the examples given in the documentation to work with CentOS 7.

### CloudFormation::Init sample on EL7

This is with the official CentOS7 AMI. You will have to replace mentions of 'SampleServer' below with the name of your resource. The example cfn configuration checks for changes to your template every 5 minutes.

```json
{
    "Mappings": {
        "AWSRegion2AMI" : {
            "ap-southeast-2": 	{ "AMI" : "ami-fedafc9d" },
            "us-east-1": 		{ "AMI" : "ami-6d1c2007" },
            "us-west-1": 		{ "AMI" : "ami-af4333cf" },
            "us-west-2": 		{ "AMI" : "ami-d2c924b2" },
            "eu-west-1": 		{ "AMI" : "ami-7abd0209" },
            "eu-central-1": 	{ "AMI" : "ami-9bf712f4" },
            "ap-south-1": 		{ "AMI" : "ami-95cda6fa" },
            "ap-southeast-1": 	{ "AMI" : "ami-f068a193" },
            "ap-northeast-1": 	{ "AMI" : "ami-eec1c380" },
            "ap-northeast-2": 	{ "AMI" : "ami-c74789a9" },
            "sa-east-1": 		{ "AMI" : "ami-26b93b4a" }
        }
    },

	"SampleServer": {
		"Type": "AWS::EC2::Instance",
		"Metadata": {
			"Comment": "Only the cfn_base section below is needed for cfn-init to work. Don't forget to change SampleServer with your actual resource name",
			"AWS::CloudFormation::Init": {
				"configSets": {
					"default": [ "cfn_base", "example_config" ]
				},
				"cfn_base": {
					"files": {
						"/etc/cfn/cfn-hup.conf": {
							"content": {"Fn::Join":["\n", [
								"[main]",
								"stack={{stackid}}",
								"region={{region}}",
								"interval=5",
								"",
								""
							]]},
							"context": {
								"stackid": {"Ref":"AWS::StackId"},
								"region": {"Ref":"AWS::Region"}
							}
						},

						"/etc/cfn/hooks.d/cfn-auto-reloader.conf": {
							"content": {"Fn::Join":["\n", [
								"[cfn-auto-reloader-hook]",
								"triggers=post.update",
								"path=Resources.SampleServer.Metadata.AWS::CloudFormation::Init",
								"action=/opt/aws/bin/cfn-init -v --stack {{stackid}} --region {{region}} --resource SampleServer",
								"runas=root",
								""
							]]},
							"context": {
								"stackid": {"Ref":"AWS::StackId"},
								"region": {"Ref":"AWS::Region"}
							}
						}
					},
					"services": {
						"sysvinit": {
							"cfn-hup": { "enabled": "true", "ensureRunning" : "true" }
						}
					}
				},
				"example_config": {
					"packages":{
						"yum": {
							"telnet": [],
							"bash-completion": [],
							"unzip": [],
							"wget": []
						}
					},
					"files":{
						"/etc/yum.repos.d/jenkins.repo": {
							"source": "http://pkg.jenkins-ci.org/redhat-stable/jenkins.repo"
						},
						"/var/tmp/jenkins-ci.org.key": {
							"source": "https://jenkins-ci.org/redhat/jenkins-ci.org.key"
						}
					},
					"commands": {
						"sample_rpm_import_command": {
							"command": "rpm --import /var/tmp/jenkins-ci.org.key",
							"test": "rpm -q gpg-pubkey-d50582e6-4a3feef6 | grep \"not installed\""
						}
					}
				}
			}
		},
		"Properties": {
			"ImageId": {"Fn::FindInMap":["AWSRegion2AMI",{"Ref":"AWS::Region"},"AMI"]},
			"Fill this here with more stuff, like InstanceType, KeyName, SecurityGroupIds and SubnetId": "",
			"UserData": {"Fn::Base64": {"Fn::Join":["", [
				"#!/bin/bash\n",
				"yum install -y epel-release\n",
				"yum install -y awscli\n",
				"/usr/bin/easy_install --script-dir /opt/aws/bin https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz\n",
				"cp -v /usr/lib/python2*/site-packages/aws_cfn_bootstrap*/init/redhat/cfn-hup /etc/init.d \n",
				"chmod +x /etc/init.d/cfn-hup \n",
				"/opt/aws/bin/cfn-init --stack ", {"Ref":"AWS::StackId"}, " --resource SampleServer --region ", {"Ref":"AWS::Region"}, "\n",
				"/opt/aws/bin/cfn-signal -e 0 --stack ", {"Ref":"AWS::StackName"}, " --resource SampleServer ",
				"    --region ", {"Ref":"AWS::Region"}, "\n"
			]]}}
		}
	}
}
```

### CodeDeploy on EL7

Example snippet of an AutoScaling LaunchConfiguration that uses CloudFormation::Init to install the CodeDeploy agent on CentOS 7, replace 'SampleLaunchConfiguration' and 'SampleAutoScalingGroup' with your actual resource name:


```json
{
    "Mappings": {
        "AWSRegion2AMI" : {
            "ap-southeast-2": 	{ "AMI" : "ami-fedafc9d" },
            "us-east-1": 		{ "AMI" : "ami-6d1c2007" },
            "us-west-1": 		{ "AMI" : "ami-af4333cf" },
            "us-west-2": 		{ "AMI" : "ami-d2c924b2" },
            "eu-west-1": 		{ "AMI" : "ami-7abd0209" },
            "eu-central-1": 	{ "AMI" : "ami-9bf712f4" },
            "ap-south-1": 		{ "AMI" : "ami-95cda6fa" },
            "ap-southeast-1": 	{ "AMI" : "ami-f068a193" },
            "ap-northeast-1": 	{ "AMI" : "ami-eec1c380" },
            "ap-northeast-2": 	{ "AMI" : "ami-c74789a9" },
            "sa-east-1": 		{ "AMI" : "ami-26b93b4a" }
        }
    },

	"SampleLaunchConfiguration": {
		"Type": "AWS::AutoScaling::LaunchConfiguration",
		"Metadata": {
			"AWS::CloudFormation::Init" : {
				"configSets": {
					"default": [ "install_base" ]
				},
				"install_base": {
					"files": {
						"/etc/cfn/cfn-hup.conf": {
							"content": {"Fn::Join":["\n", [
								"[main]",
								"stack={{stackid}}",
								"region={{region}}",
								"interval=5",
								""
							]]},
							"context": {
								"stackid": {"Ref":"AWS::StackId"},
								"region": {"Ref":"AWS::Region"}
							}
						},

						"/etc/cfn/hooks.d/cfn-auto-reloader.conf": {
							"content": {"Fn::Join":["\n", [
								"[cfn-auto-reloader-hook]",
								"triggers=post.update",
								"path=Resources.{{resource}}.Metadata.AWS::CloudFormation::Init",
								"action=/opt/aws/bin/cfn-init -v --stack {{stackid}} --region {{region}} --resource {{resource}}",
								"runas=root",
								"",
								""
							]]},
							"context": {
								"resource": "SampleLaunchConfiguration",
								"stackid": {"Ref":"AWS::StackId"},
								"region": {"Ref":"AWS::Region"}
							}
						}
					},
					"services": {
						"sysvinit": {
							"cfn-hup": { "enabled": "true", "ensureRunning" : "true" }
						}
					}
				}
			}
		},
		"Properties": {
			"ImageId": {"Fn::FindInMap":["AWSRegion2AMI",{"Ref":"AWS::Region"},"AMI"]},
			"... Fill in InstanceType, SecurityGroups, InstanceProfiles,etc here ...": "",
			"UserData": {"Fn::Base64": {"Fn::Join":["", [
				"#!/bin/bash\n",
				"yum install -y epel-release\n",
				"yum install -y awscli\n",
				"/usr/bin/easy_install --script-dir /opt/aws/bin https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz\n",
				"cp -v /usr/lib/python2*/site-packages/aws_cfn_bootstrap*/init/redhat/cfn-hup /etc/init.d \n",
				"chmod +x /etc/init.d/cfn-hup \n",
				"/opt/aws/bin/cfn-init --stack ", {"Ref":"AWS::StackId"}, " --resource SampleLaunchConfiguration --region ", {"Ref":"AWS::Region"}, " || error_exit 'Failed to run cfn-init.'\n",
				"/etc/init.d/cfn-hup start \n",
				"function handleError() {\n",
				"    /opt/aws/bin/cfn-signal -e 1 --stack ", {"Ref":"AWS::StackName"},
				"        --reason \"$1\" --resource SampleAutoScalingGroup",
				"        --region ", {"Ref":"AWS::Region"}, "\n",
				"    exit 0 \n",
				"}\n",

				"cd /tmp/ \n",
				"aws s3 cp 's3://aws-codedeploy-", {"Ref":"AWS::Region"}, "/latest/codedeploy-agent.noarch.rpm' . || handleError 'Failed to download AWS CodeDeploy Agent.'\n",
				"yum install -y ruby\n",
				"yum -y install codedeploy-agent.noarch.rpm || handleError 'Failed to yum install codedeploy-agent.noarch.rpm' \n",
				"/opt/aws/bin/cfn-signal -e 0 --stack ", {"Ref":"AWS::StackName"}, " --resource SampleAutoScalingGroup ",
				"    --region ", {"Ref":"AWS::Region"}, "\n",
				"echo Finished UserData script \n"

			]]}},
			"BlockDeviceMappings": [
				{
					"DeviceName" : "/dev/sda1",
					"Ebs": {
						"VolumeSize": "15",
						"VolumeType": "gp2"
					}
				}
			]
		}
	}

}

```

If you are using CodeDeploy with AutoScaling, and if you have issues with AutoScaling getting an ABANDONED error code during autoscaling, it's because the CodeDeploy did not finish successfully. In addition to/instead of the local /var/log/aws/codedeploy/\* logs, you can go to the CodeDeploy section in the management console, it should give you details on what went wrong. 
Unfortunately, once it fails, it's very difficult to stop it from going into a loop of retrying the deployment; and it won't even let you change the deployment revision while it's in the loop. If you want to force a success to prevent a loop, during an instance launch, you can do a:

```bash
aws autoscaling describe-lifecycle-hooks --auto-scaling-group-name YourAutoScalingGroupName
```
to find out the dynamic generated launch deployment hook, and then use that to force a success (continue) on the instance that is creating the trouble:
```bash
aws autoscaling complete-lifecycle-action --lifecycle-action-result CONTINUE  --instance-id  i-12345abcde  --lifecycle-hook-name <output-from-previous-command> --auto-scaling-group-name YourAutoScalingGroupName
```

Some other caveats of CodeDeploy you need to know about which may not be clear from the documentation: not only does CodeDeploy refuse to overwrite any files it doesn't know about, but it would actually return a deployment error. This is pretty painful, and as of writing there is no config to override this behaviour. A workaround is having something like this in your appspec.yml file:
```yaml
version: 0.0
os: linux

files:
    - source: /
      destination: /var/codedeploy

hooks:
    BeforeInstall:
        - location: codedeploy/BeforeInstall.sh
          timeout: 90
          runas: root

    AfterInstall:
        - location: codedeploy/AfterInstall.sh
          timeout: 360
          runas: root
```

which makes CodeDeploy write to it's own dedicated directory, which is emptied out in the BeforeInstall script to prevent any chance of failure:
```bash
# codedeploy/BeforeInstall.sh
set -u

CODEDEPLOY_ROOT="/var/codedeploy"

rm -rf $CODEDEPLOY_ROOT
mkdir -p $CODEDEPLOY_ROOT
```

with the actual deployment to where you want it doen in the AfterInstall bit:

```bash
# codedeploy/AfterInstall.sh
set -u

CODEDEPLOY_ROOT="/var/codedeploy"
WEB_ROOT="/var/www/html"
CODEDEPLOY_DIR="codedeploy"

# Optional Sanity check
#if [ ! -f "$CODEDEPLOY_ROOT/index.php" ]; then
#        echo "index.php does not exist in $CODEDEPLOY_ROOT, aborting"
#        exit 1
#fi

rsync --delete --delete-excluded --recursive --checksum --exclude /$CODEDEPLOY_DIR/ --exclude .git $CODEDEPLOY_ROOT/ $WEB_ROOT/
#...

```



