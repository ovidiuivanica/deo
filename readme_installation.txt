# init os packages
sudo apt-get update
sudo apt-get upgrade

# install git
sudo apt-get install git

# clone the deo repo
git clone git@github.com:ovidiuivanica/deo.git

# install serial drivers for edgeport sensors
#   download drivers from location: http://panda.moyix.net/~moyix/rpi/rpi_m ... /edgeport/
cp edgeport/* /lib/firmware/edgeport
sudo chmod +x /lib/firmware/edgeport/down3.bin

# install pip
sudo apt-get install python-pip

# install python packages
sudo pip install RPi.GPIO
sudo pip install sysv_ipc
sudo pip install pyserial
sudo pip install Django

# install deo as service
sudo systemctl edit --force deo.service

# copy the below lines to the deo.service file
[Unit]
Description=deo m@arc home automation
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python -u deoServer.py
Environment=PYTHONPATH=/home/pi
WorkingDirectory=/home/pi/deo
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target

# ui service
sudo systemctl edit --force deo_ui.service

# copy the below lines to the deo_ui.service file
[Unit]
Description=deo m@arc home automation ui
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python -u manage.py runserver 0:8000
Environment=PYTHONPATH=/home/pi
WorkingDirectory=/home/pi/deo/ui
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target

# enable the newly created services
sudo systemctl enable deo.service
sudo systemctl enable deo_ui.service

# start the services
sudo systemctl start deo
sudo systemctl start deo_ui

# enjoy