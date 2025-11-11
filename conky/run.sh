for cfg in ~/thomas_config/conky/*.conf; do
  conky --daemonize --pause=1 -c "$cfg"
done
