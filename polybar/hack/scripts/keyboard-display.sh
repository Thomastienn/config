#!/usr/bin/env bash
engine=$(ibus engine)
case $engine in
    Unikey)
        echo "  Unikey"
        ;;
    *us*)
        echo "  US"
        ;;
    *)
        echo "   ${engine##*:}"  # Shows last part after colon
        ;;
esac
