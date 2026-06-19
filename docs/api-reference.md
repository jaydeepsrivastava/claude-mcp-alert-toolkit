# API Reference — curl Command Templates

## Environment Variables
| Variable | Used For |
|---|---|
| `PAGERDUTY_API_KEY` | PagerDuty REST API auth |
| `CHECKMK_USER` | CheckMK automation user |
| `CHECKMK_SECRET` | CheckMK automation password |

Load: `set -a && source /home/jaydeep/jaydeep_claude/.env && set +a`

## PagerDuty

```bash
# Fetch incident
curl -s -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     "https://api.pagerduty.com/incidents/[INCIDENT_ID]"

# List active incidents
curl -s -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     "https://api.pagerduty.com/incidents?statuses[]=triggered&statuses[]=acknowledged"

# Fetch incident notes
curl -s -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     "https://api.pagerduty.com/incidents/[INCIDENT_ID]/notes"

# Write resolution note back
curl -s -X POST \
     -H "Authorization: Token token=$PAGERDUTY_API_KEY" \
     -H "Accept: application/vnd.pagerduty+json;version=2" \
     -H "Content-Type: application/json" \
     -H "From: jaydeep.srivastava@8x8.com" \
     -d "{\"note\": {\"content\": \"[RESOLUTION STEPS]\"}}" \
     "https://api.pagerduty.com/incidents/[INCIDENT_ID]/notes"
```

## CheckMK

```bash
# Get service status
curl -s -u "$CHECKMK_USER:$CHECKMK_SECRET" \
     "https://[CHECKMK_HOST]/[SITE]/api/1.0/objects/service/[HOST]~[SERVICE]"

# List recent problems (state=2 = CRIT)
curl -s -u "$CHECKMK_USER:$CHECKMK_SECRET" \
     "https://[CHECKMK_HOST]/[SITE]/api/1.0/domain-types/service/collections/all?query={\"op\":\"=\",\"left\":\"state\",\"right\":\"2\"}"
```
