CURRENT_PRIME=$(prime-select query | awk '{print toupper(substr($0,1,1)) tolower(substr($0,2))}')
echo " ${CURRENT_PRIME}"



