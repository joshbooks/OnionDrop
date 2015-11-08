#! /bin/bash
#This script looks through the system for all directories
#containing the filenames "hostname" and "private_key"
#and checks if you have the message packs that correspond
#with any of those hidden service directories and if
#so decrypts them and and displays them immediately
#so they are never written to file as plaintext
#the script must be run as root, so I would advise
#against running it on a production server
if [[ `whoami` != "root" ]]
then
	echo "this script should be run as root"
	exit
fi

read -ra prelim <<< `find / -path */hostname`
for i in ${prelim[@]}
do
	if [[ -e "`dirname $i`/private_key" ]]
	then
		 dirs+=("$(dirname $i)")
	fi
done

if [[ ${#dirs[@]} = 0 ]]
then
	echo "It looks like you aren't running any hidden services, this tool isn't for you :("
	exit
fi

for i in ${dirs[@]}
do
	host=$(cat $i/hostname)
	hosts+=host
	cat  $i/private_key > "$host.key"
done


for i in ${hosts[@]}
do
	path=$(find / -path "*$host.tar.gz" )
	tar -xzf $path
	mkdir -p $host
	read -ra files <<< $(tar -tzf $path)
	for j in ${files[@]}
	do
		mv "./$j" ./$host
		cat "./$host/$j" | openssl rsautl -decrypt -inkey "$host.key" -raw | less
	done
	rm "$host.key"
	rm -rf "./$host/"
done
