#!/bin/sh
sudo docker run --restart=unless-stopped --env-file=.env -it -v $HOME/.karmabot/:/app karmabot