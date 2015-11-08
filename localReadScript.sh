#! /bin/bash
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
