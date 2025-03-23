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
        # add also AmazonEKS_CNI_Policy and AmazonEC2ContainerRegistryReadOnly
        self.role_policy_attachment = aws.iam.RolePolicyAttachment(f"{prefix}-role-policy-attachment-2",
                                                                  policy_arn="arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
                                                                  role=self.role.name,
            opts=pulumi.ResourceOptions(provider=opts.provider))
        self.role_policy_attachment = aws.iam.RolePolicyAttachment(f"{prefix}-role-policy-attachment-3",
                                                                  policy_arn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
                                                                  role=self.role.name,
            opts=pulumi.ResourceOptions(provider=opts.provider))
        # add also AmazonEC2ReadOnlyAccess
        self.role_policy_attachment = aws.iam.RolePolicyAttachment(f"{prefix}-role-policy-attachment-4",
                                                                  policy_arn="arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess",
                                                                  role=self.role.name,
            opts=pulumi.ResourceOptions(provider=opts.provider  ))
        # and create a custom policy to allow all actions on elasticloadbalancing
        self.policy = aws.iam.Policy(f"{prefix}-policy",
                                    policy="""{
                                        "Version": "2012-10-17",
                                        "Statement": [
                                          {
                                              "Action": "elasticloadbalancing:*",
                                              "Effect": "Allow",
                                              "Resource": "*"
                                          },
                                          {
                                              "Action": "iam:CreateServiceLinkedRole",
                                              "Effect": "Allow",
                                              "Resource": "*"
                                          },
                                          {
                                              "Action": "ec2:AuthorizeSecurityGroupIngress",
                                              "Effect": "Allow",
                                              "Resource": "*"
                                          }
                                        ]
                                    }""",
                                    opts=pulumi.ResourceOptions(provider=opts.provider))
        # attach the custom policy to the role
        self.role_policy_attachment = aws.iam.RolePolicyAttachment(f"{prefix}-role-policy-attachment-5",
                                                                  policy_arn=self.policy.arn,
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
      installFlags:
        - --enable-cloud-provider
        - --kubelet-extra-args="--cloud-provider=external"
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
    k0s:
      config:
        apiVersion: k0s.k0sproject.io/v1beta1
        kind: ClusterConfig
        metadata:
          name: k0s
          namespace: kube-system
        spec:
          extensions:
            helm:
              concurrencyLevel: 5
              repositories:
              - name: aws-cloud-controller-manager
                url: https://kubernetes.github.io/cloud-provider-aws
              charts:
              - name: aws-cloud-controller-manager
                chartname: aws-cloud-controller-manager/aws-cloud-controller-manager
                version: "0.0.8"
                timeout: 10m
                order: 1
                namespace: kube-system
                values: |
                  args:
                    - --v=2
                    - --cloud-provider=aws
                    - --configure-cloud-routes=false
                  nodeSelector:
                    kubernetes.io/os: linux
                    node-role.kubernetes.io/control-plane: null
          network:
            clusterDomain: cluster.local
            dualStack:
              enabled: false
            kubeProxy:
              iptables:
                minSyncPeriod: 0s
                syncPeriod: 0s
              ipvs:
                minSyncPeriod: 0s
                syncPeriod: 0s
                tcpFinTimeout: 0s
                tcpTimeout: 0s
                udpTimeout: 0s
              metricsBindAddress: 0.0.0.0:10249
              mode: iptables
              nftables:
                minSyncPeriod: 0s
                syncPeriod: 0s
            nodeLocalLoadBalancing:
              enabled: false
              envoyProxy:
                apiServerBindPort: 7443
                konnectivityServerBindPort: 7132
              type: EnvoyProxy
            podCIDR: 10.244.0.0/16
            provider: calico
            serviceCIDR: 10.96.0.0/12
          scheduler: {{}}
          storage:
            etcd:
              peerAddress: 10.0.1.10
            type: etcd
          telemetry:
            enabled: true
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
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh
chown -R ec2-user:ec2-user /home/ec2-user
            """

        self.instance = aws.ec2.Instance(f"{prefix}-ec2",
                                         ami="ami-053a45fff0a704a47",
                                         instance_type="t3.micro",
                                         vpc_security_group_ids=[networkingComponent.security_group.id],
                                         subnet_id=networkingComponent.subnet.id,
                                         tags={"Name": f"{name}-instance", "kubernetes.io/cluster/k0s": "owned"},
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
