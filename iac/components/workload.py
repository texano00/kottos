import pulumi
import pulumi_aws as aws
from components.networking import NetworkingComponent


class WorkloadComponent(pulumi.ComponentResource):
    def __init__(self, name, networkingComponent: NetworkingComponent, ssh_key_pair, worker_ips=[], opts=None):

        super().__init__('pkg:index:WorkloadComponent', name, None, opts)
        prefix = f"{name}-{networkingComponent.index}"
        self.public_key = ssh_key_pair[0]
        self.private_key = ssh_key_pair[1]

        # create a role
        self.role = aws.iam.Role(f"{prefix}-role",
                                    assume_role_policy="""{
                                        "Version": "2012-10-17",
                                        "Statement": [
                                            {
                                                "Effect": "Allow",
                                                "Principal": {
                                                    "Service": "ec2.amazonaws.com"
                                                },
                                                "Action": "sts:AssumeRole"
                                            }
                                        ]
                                    }""",
                                    opts=pulumi.ResourceOptions(provider=opts.provider))
        # attach the AmazonSSMManagedInstanceCore policy to the role
        self.role_policy_attachment = aws.iam.RolePolicyAttachment(f"{prefix}-role-policy-attachment",
                                                                  policy_arn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
                                                                  role=self.role.name,
            opts=pulumi.ResourceOptions(provider=opts.provider))
        
        # create an instance profile
        self.instance_profile = aws.iam.InstanceProfile(f"{prefix}-instance-profile",
                                                        role=self.role.name,
                                                        opts=pulumi.ResourceOptions(provider=opts.provider))
        self.private_ip = ".".join(networkingComponent.subnet_cidr.split(".")[:3]) + ".10"

        additional_user_data = ""
        if name == "master":
            # iterate over the worker_ips list and add the worker nodes
            workers = ""
            for i, worker_ip in enumerate(worker_ips):
                workers += f"""
    - ssh:
        address: {worker_ip}
        user: ec2-user
        port: 22
        keyPath: ~/.ssh/id_rsa
      role: worker
                """

            additional_user_data = f"""
sudo su - ec2-user
export HOME=/home/ec2-user
wget https://github.com/k0sproject/k0sctl/releases/download/v0.23.0/k0sctl-linux-amd64 -O k0sctl
chmod +x k0sctl
sudo install k0sctl /usr/local/bin
echo \"\"\"
apiVersion: k0sctl.k0sproject.io/v1beta1
kind: Cluster
metadata:
    name: k0s-cluster
    user: admin
spec:
    hosts:
    - ssh:
        address: {self.private_ip}
        user: ec2-user
        port: 22
        keyPath: ~/.ssh/id_rsa
      role: controller
    {workers}
\"\"\" > /home/ec2-user/k0s-cluster.yaml
k0sctl apply -d --config /home/ec2-user/k0s-cluster.yaml

curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client
mkdir /home/ec2-user/.kube
chown -R ec2-user:ec2-user /home/ec2-user
            """

        self.instance = aws.ec2.Instance(f"{prefix}-ec2",
                                         ami="ami-053a45fff0a704a47",
                                         instance_type="t3.micro",
                                         vpc_security_group_ids=[networkingComponent.security_group.id],
                                         subnet_id=networkingComponent.subnet.id,
                                         tags={"Name": f"{name}-instance"},
                                         private_ip=self.private_ip,
                                         # add userdata to setup ssh public and private key, add the public key to the authorized_keys file
                                         user_data=f"""#!/bin/bash
                                            echo "{self.public_key}" > /home/ec2-user/.ssh/authorized_keys
                                            echo "{self.private_key}" > /home/ec2-user/.ssh/id_rsa
                                            echo "{self.public_key}" > /home/ec2-user/.ssh/id_rsa.pub
                                            chmod 600 /home/ec2-user/.ssh/id_rsa
                                            chmod 644 /home/ec2-user/.ssh/authorized_keys
                                            chown ec2-user:ec2-user /home/ec2-user/.ssh/authorized_keys
                                            chown ec2-user:ec2-user /home/ec2-user/.ssh/id_rsa
                                            {additional_user_data}
                                         """,

                                         iam_instance_profile=self.instance_profile.name,
            opts=pulumi.ResourceOptions(provider=opts.provider, depends_on=opts.depends_on))
        
        self.register_outputs({
            "instance_id": self.instance.id
        })
