import os
import subprocess

def generate_ssh_keys():
    private_key_path = "/tmp/id_rsa"
    public_key_path = f"{private_key_path}.pub"

    # Generate SSH key pair
    subprocess.run([
        "ssh-keygen", "-t", "rsa", "-b", "2048", "-f", private_key_path, "-q", "-N", ""
    ], check=True)

    # Read the keys
    with open(private_key_path, "r") as private_key_file:
        private_key = private_key_file.read()

    with open(public_key_path, "r") as public_key_file:
        public_key = public_key_file.read()

    # Remove the keys
    os.remove(private_key_path)
    os.remove(public_key_path)
    
    return public_key, private_key