#!/usr/bin/env python3
# day_trader_pro/check_iam.py — v0.1.0
"""
Verifies the reporter's IAM instance role can see and control the
day_trader fleet. Read-only: it never starts or stops anything.

Usage:
    python3 check_iam.py
"""

import sys

REGION = "us-east-2"
TAG_KEY = "Project"
TAG_VAL = "day_trader"


def main():
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ClientError
    except ImportError:
        print("boto3 not installed in this environment. Run: pip install boto3")
        return 1

    ec2 = boto3.client("ec2", region_name=REGION)

    # Confirm we actually have role credentials before making the call.
    try:
        ident = boto3.client("sts", region_name=REGION).get_caller_identity()
        print(f"credentials OK — acting as: {ident['Arn']}")
    except NoCredentialsError:
        print("NO CREDENTIALS: the IAM role is not attached to THIS instance yet.")
        print("  -> EC2 > select 1-REPORTER > Actions > Security > Modify IAM role")
        return 1
    except ClientError as exc:
        print(f"STS error: {exc}")
        return 1

    try:
        resp = ec2.describe_instances(
            Filters=[{"Name": f"tag:{TAG_KEY}", "Values": [TAG_VAL]}]
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UnauthorizedOperation":
            print("UNAUTHORIZED: role is attached but the policy is missing "
                  "ec2:DescribeInstances. Recheck the policy JSON.")
        else:
            print(f"describe_instances failed: {code} — {exc}")
        return 1

    rows = []
    for res in resp.get("Reservations", []):
        for inst in res.get("Instances", []):
            name = next((t["Value"] for t in inst.get("Tags", [])
                         if t["Key"] == "Name"), "?")
            rows.append((name, inst["InstanceId"], inst["State"]["Name"]))

    rows.sort()
    print(f"\nrole works — sees {len(rows)} '{TAG_VAL}' instances in {REGION}:\n")
    print(f"  {'TAG NAME':<10}{'INSTANCE ID':<24}STATE")
    for name, iid, state in rows:
        print(f"  {name:<10}{iid:<24}{state}")

    if len(rows) == 0:
        print("\n  0 found. Check: tag key is exactly 'Project', value exactly "
              "'day_trader' (case-sensitive), and boxes are in us-east-2.")
    else:
        print(f"\n  Expecting ~30. Got {len(rows)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
