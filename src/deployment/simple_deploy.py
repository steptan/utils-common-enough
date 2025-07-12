#!/usr/bin/env python3
"""
Simple deployment script for Media Register that generates CloudFormation template.
This version doesn't require AWS CDK.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


def create_cloudformation_template(environment: str = "dev") -> Dict[str, Any]:
    """Create a CloudFormation template for Media Register."""

    stack_name: str = f"media-register-{environment}"

    template: Dict[str, Any] = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": f"Media Register Application - {environment}",
        "Parameters": {
            "Environment": {
                "Type": "String",
                "Default": environment,
                "Description": "Environment name",
            }
        },
        "Resources": {},
        "Outputs": {},
    }

    # Add Cognito User Pool
    template["Resources"]["UserPool"] = {
        "Type": "AWS::Cognito::UserPool",
        "Properties": {
            "UserPoolName": f"{stack_name}-users",
            "UsernameAttributes": ["email"],
            "AutoVerifiedAttributes": ["email"],
            "Schema": [
                {
                    "Name": "email",
                    "AttributeDataType": "String",
                    "Required": True,
                    "Mutable": False,
                },
                {
                    "Name": "name",
                    "AttributeDataType": "String",
                    "Required": True,
                    "Mutable": True,
                },
            ],
            "Policies": {
                "PasswordPolicy": {
                    "MinimumLength": 8,
                    "RequireUppercase": True,
                    "RequireLowercase": True,
                    "RequireNumbers": True,
                }
            },
        },
    }

    # Add User Pool Client
    template["Resources"]["UserPoolClient"] = {
        "Type": "AWS::Cognito::UserPoolClient",
        "Properties": {
            "ClientName": f"{stack_name}-web-client",
            "UserPoolId": {"Ref": "UserPool"},
            "GenerateSecret": False,
            "ExplicitAuthFlows": [
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
            ],
        },
    }

    # Add DynamoDB Table
    template["Resources"]["DynamoDBTable"] = {
        "Type": "AWS::DynamoDB::Table",
        "Properties": {
            "TableName": f"{stack_name}-media",
            "BillingMode": "PAY_PER_REQUEST",
            "AttributeDefinitions": [
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
            ],
            "KeySchema": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "gsi1",
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            "StreamSpecification": {"StreamViewType": "NEW_AND_OLD_IMAGES"},
        },
    }

    # Add S3 Buckets
    template["Resources"]["UploadBucket"] = {
        "Type": "AWS::S3::Bucket",
        "Properties": {
            "BucketName": f"{stack_name}-uploads-{os.urandom(8).hex()}",
            "CorsConfiguration": {
                "CorsRules": [
                    {
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
                        "AllowedOrigins": ["*"],
                        "MaxAge": 3600,
                    }
                ]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    }

    template["Resources"]["WebsiteBucket"] = {
        "Type": "AWS::S3::Bucket",
        "Properties": {
            "BucketName": f"{stack_name}-website-{os.urandom(8).hex()}",
            "WebsiteConfiguration": {
                "IndexDocument": "index.html",
                "ErrorDocument": "error.html",
            },
        },
    }

    # Add Lambda Execution Role
    template["Resources"]["LambdaExecutionRole"] = {
        "Type": "AWS::IAM::Role",
        "Properties": {
            "RoleName": f"{stack_name}-lambda-role",
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            "ManagedPolicyArns": [
                "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ],
            "Policies": [
                {
                    "PolicyName": "DynamoDBAccess",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "dynamodb:GetItem",
                                    "dynamodb:PutItem",
                                    "dynamodb:UpdateItem",
                                    "dynamodb:DeleteItem",
                                    "dynamodb:Query",
                                    "dynamodb:Scan",
                                ],
                                "Resource": [
                                    {"Fn::GetAtt": ["DynamoDBTable", "Arn"]},
                                    {"Fn::Sub": "${DynamoDBTable.Arn}/index/*"},
                                ],
                            }
                        ],
                    },
                },
                {
                    "PolicyName": "S3Access",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "s3:GetObject",
                                    "s3:PutObject",
                                    "s3:DeleteObject",
                                ],
                                "Resource": [{"Fn::Sub": "${UploadBucket.Arn}/*"}],
                            }
                        ],
                    },
                },
            ],
        },
    }

    # Add a sample Lambda function
    template["Resources"]["HealthCheckFunction"] = {
        "Type": "AWS::Lambda::Function",
        "Properties": {
            "FunctionName": f"{stack_name}-healthCheck",
            "Runtime": "nodejs18.x",
            "Handler": "index.handler",
            "Role": {"Fn::GetAtt": ["LambdaExecutionRole", "Arn"]},
            "Code": {
                "ZipFile": """
exports.handler = async (event) => {
    return {
        statusCode: 200,
        headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({
            status: 'healthy',
            timestamp: new Date().toISOString(),
            service: 'media-register-api'
        })
    };
};
"""
            },
            "Environment": {
                "Variables": {
                    "ENVIRONMENT": environment,
                    "DYNAMODB_TABLE": {"Ref": "DynamoDBTable"},
                }
            },
        },
    }

    # Add API Gateway
    template["Resources"]["ApiGateway"] = {
        "Type": "AWS::ApiGateway::RestApi",
        "Properties": {
            "Name": f"{stack_name}-api",
            "Description": "Media Register API",
            "EndpointConfiguration": {"Types": ["REGIONAL"]},
        },
    }

    # Add health resource
    template["Resources"]["HealthResource"] = {
        "Type": "AWS::ApiGateway::Resource",
        "Properties": {
            "ParentId": {"Fn::GetAtt": ["ApiGateway", "RootResourceId"]},
            "PathPart": "health",
            "RestApiId": {"Ref": "ApiGateway"},
        },
    }

    # Add health method
    template["Resources"]["HealthMethod"] = {
        "Type": "AWS::ApiGateway::Method",
        "Properties": {
            "AuthorizationType": "NONE",
            "HttpMethod": "GET",
            "ResourceId": {"Ref": "HealthResource"},
            "RestApiId": {"Ref": "ApiGateway"},
            "Integration": {
                "Type": "AWS_PROXY",
                "IntegrationHttpMethod": "POST",
                "Uri": {
                    "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${HealthCheckFunction.Arn}/invocations"
                },
            },
        },
    }

    # Add Lambda permission for API Gateway
    template["Resources"]["HealthCheckApiPermission"] = {
        "Type": "AWS::Lambda::Permission",
        "Properties": {
            "FunctionName": {"Ref": "HealthCheckFunction"},
            "Action": "lambda:InvokeFunction",
            "Principal": "apigateway.amazonaws.com",
            "SourceArn": {
                "Fn::Sub": "arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${ApiGateway}/*/*/*"
            },
        },
    }

    # Add API deployment
    template["Resources"]["ApiDeployment"] = {
        "Type": "AWS::ApiGateway::Deployment",
        "DependsOn": ["HealthMethod"],
        "Properties": {"RestApiId": {"Ref": "ApiGateway"}, "StageName": environment},
    }

    # Add CloudFront distribution
    template["Resources"]["CloudFrontDistribution"] = {
        "Type": "AWS::CloudFront::Distribution",
        "Properties": {
            "DistributionConfig": {
                "Origins": [
                    {
                        "Id": "S3Origin",
                        "DomainName": {
                            "Fn::GetAtt": ["WebsiteBucket", "RegionalDomainName"]
                        },
                        "S3OriginConfig": {"OriginAccessIdentity": ""},
                    },
                    {
                        "Id": "ApiOrigin",
                        "DomainName": {
                            "Fn::Sub": "${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com"
                        },
                        "CustomOriginConfig": {
                            "HTTPPort": 80,
                            "HTTPSPort": 443,
                            "OriginProtocolPolicy": "https-only",
                        },
                        "OriginPath": f"/{environment}",
                    },
                ],
                "Enabled": True,
                "DefaultRootObject": "index.html",
                "DefaultCacheBehavior": {
                    "TargetOriginId": "S3Origin",
                    "ViewerProtocolPolicy": "redirect-to-https",
                    "AllowedMethods": ["GET", "HEAD"],
                    "CachedMethods": ["GET", "HEAD"],
                    "ForwardedValues": {
                        "QueryString": False,
                        "Cookies": {"Forward": "none"},
                    },
                },
                "CacheBehaviors": [
                    {
                        "PathPattern": "/api/*",
                        "TargetOriginId": "ApiOrigin",
                        "ViewerProtocolPolicy": "redirect-to-https",
                        "AllowedMethods": [
                            "GET",
                            "HEAD",
                            "OPTIONS",
                            "PUT",
                            "POST",
                            "PATCH",
                            "DELETE",
                        ],
                        "CachedMethods": ["GET", "HEAD"],
                        "ForwardedValues": {
                            "QueryString": True,
                            "Headers": ["Authorization", "Content-Type"],
                            "Cookies": {"Forward": "none"},
                        },
                    }
                ],
                "PriceClass": "PriceClass_100",
            }
        },
    }

    # Add Outputs
    template["Outputs"] = {
        "UserPoolId": {
            "Description": "Cognito User Pool ID",
            "Value": {"Ref": "UserPool"},
        },
        "UserPoolClientId": {
            "Description": "Cognito User Pool Client ID",
            "Value": {"Ref": "UserPoolClient"},
        },
        "ApiUrl": {
            "Description": "API Gateway URL",
            "Value": {
                "Fn::Sub": f"https://${{ApiGateway}}.execute-api.${{AWS::Region}}.amazonaws.com/{environment}"
            },
        },
        "WebsiteUrl": {
            "Description": "CloudFront Distribution URL",
            "Value": {"Fn::Sub": "https://${CloudFrontDistribution.DomainName}"},
        },
        "WebsiteBucket": {
            "Description": "S3 Bucket for website hosting",
            "Value": {"Ref": "WebsiteBucket"},
        },
        "UploadBucket": {
            "Description": "S3 Bucket for file uploads",
            "Value": {"Ref": "UploadBucket"},
        },
        "CloudFrontDistributionId": {
            "Description": "CloudFront Distribution ID",
            "Value": {"Ref": "CloudFrontDistribution"},
        },
    }

    return template


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Deploy Media Register application")
    parser.add_argument(
        "--environment",
        "-e",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Deployment environment",
    )
    parser.add_argument(
        "--output", "-o", help="Output file for CloudFormation template"
    )

    args = parser.parse_args()

    # Generate template
    template = create_cloudformation_template(args.environment)

    # Output template
    if args.output:
        with open(args.output, "w") as f:
            json.dump(template, f, indent=2)
        print(f"CloudFormation template written to {args.output}")
    else:
        print(json.dumps(template, indent=2))


if __name__ == "__main__":
    main()
