sudo apt-get install -y libasound2-dev libportaudio2 libportaudiocpp0 portaudio19-dev python3-dev python3-venv python3-pip
mkdir ~/assistant-bridge
cd ~/assistant-bridge
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo vi /etc/systemd/system/private-assistant-bridge-client.service
sudo systemctl enable --now private-assistant-bridge-client.service
journalctl -f -u private-assistant-bridge-client
