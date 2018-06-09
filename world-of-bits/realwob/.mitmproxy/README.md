## Keys in a repo?

These keys are used by the proxy server to establish TLS connection with browser. Since this is a simulated environment, these are not real keys. We are not worried about spoofing.

## Steps to setup mitmproxy

1. run `pip install vendor/mitmproxy`.
2. copy `.mitmproxy` to `~/`.
3. install the certifcates for target browswer - add `mitmproxy-ca-cert.pem` to keychain.