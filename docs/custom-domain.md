# Using your own DNS domain (removing the SSL cert warning)

The default `<ip>.nip.io` hostname works but some clients warn about the
cert being for a domain that "isn't yours". With a real domain you own,
the browser sees a fully-trusted Google-managed cert.

## Prerequisites

- A domain (or subdomain) whose DNS you control. Example:
  `antigravity.customertests.info`.
- The LB's static IP already reserved (run `scripts/gcp_setup_lb.sh` once
  with just `PUBLIC_HOSTNAME` set — this reserves the IP even before the
  cert can validate).

## Setup

### 1. Reserve the static IP (if you haven't yet)

```bash
scripts/gcp_setup_lb.sh
```

Read the output for `reserved IP=…`. That's what your DNS record points at.
The first run also provisions an nip.io cert; that's fine — we'll swap it.

### 2. Create the DNS A record

In whatever DNS zone you own:

```
antigravity.customertests.info.  300  IN  A  <the-reserved-IP>
```

Wait for it to propagate. Test:

```bash
dig +short antigravity.customertests.info
# should print the LB IP
```

### 3. Set PUBLIC_DOMAIN in .env

```bash
echo 'PUBLIC_DOMAIN=antigravity.customertests.info' >> .env
```

### 4. Re-run the LB setup script

```bash
scripts/gcp_setup_lb.sh
```

It will:

- Create a new Google-managed SSL cert
  `antigravity-web-cert-antigravity-customertests-info` for that hostname.
- Swap the target-https-proxy to use the new cert (the old nip.io cert
  stays around, harmless — you can delete it manually if you want).
- Cert validation begins immediately but Google's ACME dance takes ~15–60
  minutes on first issuance. Track it with:

```bash
gcloud compute ssl-certificates describe \
  antigravity-web-cert-antigravity-customertests-info \
  --global --format='value(managed.status,managed.domainStatus)'
```

Wait until status is `ACTIVE` and each domain shows `ACTIVE`.

### 5. Test

Open `https://antigravity.customertests.info/`. Cert should be fully
trusted, no browser warning.

## Multi-domain (optional)

If you want both the nip.io form and your custom domain to work
simultaneously, edit the `--domains=` flag in `gcp_setup_lb.sh` to pass
both, e.g. `--domains=antigravity.customertests.info,${IP}.nip.io`.

## Rotating to a different domain later

Change `PUBLIC_DOMAIN` in `.env`, re-run `scripts/gcp_setup_lb.sh`. The
script computes the cert name from the hostname, so a new cert is created
for the new name and the target proxy is swapped over automatically. The
old cert can be deleted with:

```bash
gcloud compute ssl-certificates delete antigravity-web-cert-<old-slug> --global
```

## Why nip.io shows a warning sometimes

nip.io itself has a valid cert (it's a legit service), and Google-managed
certs for `<ip>.nip.io` do provision correctly. The occasional warning
some folks see comes from:

- Corporate SSL-inspecting proxies that don't trust unusual TLDs.
- Cert still in `PROVISIONING` on the first ~30 min after LB setup.
- Ad-blocker / privacy extensions that flag nip.io as suspicious.

Your own domain avoids all three.
