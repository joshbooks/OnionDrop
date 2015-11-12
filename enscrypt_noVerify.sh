#!/bin/bash
#script to locally encrypt a message for onion drop
#if you really really want to you can recompute the
#hash of the public key and make sure it back comes out 
#to the correct hostname, check the following webpage for
#details:
#https://trac.torproject.org/projects/tor/wiki/doc/HiddenServiceNames
#only checks that curl and openssl are installed, assumes
#tor socksPort is running on port 9050
if [[ $# != 1 ]]
then
  echo "Usage: $0 .onion-domain"
  exit
fi
host=$1
if [[ ! -e `which openssl` ]]
then
  echo "openssl must be installed for this script to work"
  exit
fi
if [[ ! -e `which curl` ]]
then
  echo "curl must be installed for this script to work"
  exit
fi

curl -L --socks5-hostname localhost:9050 "oniondropodx6dyg.onion/key/$host" > ./"$host.tmp.pem"
openssl rsa -pubin -RSAPublicKey_in -in ./"$host.tmp.pem" > ./"$host.pem"
rm ./"$host.tmp.pem"
echo "to encrypt a message with this key use the following command:"
echo "openssl rsautl -encrypt -pubin -inkey $host.pem -in yourMessageFileHere"


