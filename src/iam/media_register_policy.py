"""
Minimal CI/CD policy for media-register project.
This policy is optimized for size to stay under AWS's 6KB limit.
"""

def get_media_register_cicd_policy(account_id: str, region: str = "us-west-1") -> dict:
    """
    Get a minimal CI/CD policy for media-register.
    
    This policy excludes VPC-related permissions since media-register
    runs Lambda functions without VPC for cost optimization.
    """
    return {
        "Version": "2012-10-17",
        "Statement": [
            # CloudFormation - minimal permissions
            {
                "Sid": "CFN",
                "Effect": "Allow",
                "Action": [
                    "cloudformation:*"
                ],
                "Resource": [
                    f"arn:aws:cloudformation:{region}:{account_id}:stack/media-register-*/*",
                    f"arn:aws:cloudformation:{region}:aws:transform/*"
                ]
            },
            # S3 - for Lambda deployment and frontend
            {
                "Sid": "S3",
                "Effect": "Allow",
                "Action": [
                    "s3:*"
                ],
                "Resource": [
                    "arn:aws:s3:::media-register-*",
                    "arn:aws:s3:::media-register-*/*"
                ]
            },
            # Lambda - without VPC permissions
            {
                "Sid": "Lambda",
                "Effect": "Allow",
                "Action": [
                    "lambda:*"
                ],
                "Resource": f"arn:aws:lambda:{region}:{account_id}:function:media-register-*"
            },
            # IAM - for Lambda execution roles
            {
                "Sid": "IAM",
                "Effect": "Allow",
                "Action": [
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRole",
                    "iam:GetRolePolicy",
                    "iam:PassRole",
                    "iam:TagRole",
                    "iam:UntagRole"
                ],
                "Resource": [
                    f"arn:aws:iam::{account_id}:role/media-register-*"
                ]
            },
            # API Gateway
            {
                "Sid": "API",
                "Effect": "Allow",
                "Action": [
                    "apigateway:*"
                ],
                "Resource": [
                    f"arn:aws:apigateway:{region}::/restapis",
                    f"arn:aws:apigateway:{region}::/restapis/*"
                ]
            },
            # DynamoDB
            {
                "Sid": "DDB",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:CreateTable",
                    "dynamodb:DeleteTable",
                    "dynamodb:DescribeTable",
                    "dynamodb:UpdateTable",
                    "dynamodb:TagResource",
                    "dynamodb:UntagResource",
                    "dynamodb:ListTagsOfResource",
                    "dynamodb:UpdateTimeToLive",
                    "dynamodb:DescribeTimeToLive"
                ],
                "Resource": f"arn:aws:dynamodb:{region}:{account_id}:table/media-register-*"
            },
            # CloudFront
            {
                "Sid": "CF",
                "Effect": "Allow",
                "Action": [
                    "cloudfront:CreateDistribution",
                    "cloudfront:UpdateDistribution",
                    "cloudfront:DeleteDistribution",
                    "cloudfront:GetDistribution",
                    "cloudfront:TagResource",
                    "cloudfront:UntagResource",
                    "cloudfront:CreateInvalidation"
                ],
                "Resource": "*"
            },
            # CloudWatch Logs
            {
                "Sid": "Logs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:DeleteLogGroup",
                    "logs:PutRetentionPolicy",
                    "logs:TagResource",
                    "logs:UntagResource"
                ],
                "Resource": f"arn:aws:logs:{region}:{account_id}:log-group:/aws/lambda/media-register-*"
            },
            # Cognito
            {
                "Sid": "Cognito",
                "Effect": "Allow",
                "Action": [
                    "cognito-idp:CreateUserPool",
                    "cognito-idp:DeleteUserPool",
                    "cognito-idp:UpdateUserPool",
                    "cognito-idp:DescribeUserPool",
                    "cognito-idp:CreateUserPoolClient",
                    "cognito-idp:DeleteUserPoolClient",
                    "cognito-idp:UpdateUserPoolClient"
                ],
                "Resource": "*"
            },
            # WAF (optional)
            {
                "Sid": "WAF",
                "Effect": "Allow",
                "Action": [
                    "wafv2:CreateWebACL",
                    "wafv2:DeleteWebACL",
                    "wafv2:UpdateWebACL",
                    "wafv2:GetWebACL",
                    "wafv2:AssociateWebACL",
                    "wafv2:DisassociateWebACL"
                ],
                "Resource": "*"
            },
            # Tags
            {
                "Sid": "Tags",
                "Effect": "Allow",
                "Action": [
                    "tag:GetResources",
                    "tag:TagResources",
                    "tag:UntagResources"
                ],
                "Resource": "*"
            }
        ]
    }