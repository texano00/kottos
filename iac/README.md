

# Misc
curl -sSLf https://get.k0s.sh | sudo sh

wget https://github.com/k0sproject/k0sctl/releases/download/v0.23.0/k0sctl-linux-amd64 -O k0sctl
chmod +x k0sctl
sudo install k0sctl /usr/local/bin

echo """
apiVersion: k0sctl.k0sproject.io/v1beta1
kind: Cluster
metadata:
  name: k0s-cluster
  user: admin
spec:
  hosts:
  - ssh:
      address: 10.0.1.144
      user: ec2-user
      port: 22
      keyPath: ~/.ssh/id_rsa
    role: controller
  - ssh:
      address: 10.1.1.128
      user: ec2-user
      port: 22
      keyPath: ~/.ssh/id_rsa
    role: worker
""" > k0s-cluster.yaml

k0sctl apply --config k0s-cluster.yaml

curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client

mkdir ~/.kube
k0sctl kubeconfig --config k0s-cluster.yaml > ~/.kube/config
alias k = kubectl