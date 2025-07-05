# IAM Permissions Analysis

This document analyzes the permissions granted by the unified permissions script compared to all available permissions for key AWS services.

## Summary

| Service    | Total Available Actions | Actions Granted | Actions NOT Granted | Coverage |
| ---------- | ----------------------- | --------------- | ------------------- | -------- |
| VPC (EC2)  | ~400+                   | 59              | 340+                | ~15%     |
| S3         | ~100+                   | 26              | 74+                 | ~26%     |
| Lambda     | ~70+                    | 24              | 46+                 | ~34%     |
| DynamoDB   | ~50+                    | 20              | 30+                 | ~40%     |
| CloudFront | ~40+                    | 18              | 22+                 | ~45%     |

## Detailed Analysis

### VPC (EC2) Permissions

#### Currently Granted (59 actions):

- **VPC Management**: CreateVpc, DeleteVpc, ModifyVpcAttribute, DescribeVpcs
- **Subnet Management**: CreateSubnet, DeleteSubnet, ModifySubnetAttribute, DescribeSubnets
- **Internet Gateway**: CreateInternetGateway, DeleteInternetGateway, AttachInternetGateway, DetachInternetGateway, DescribeInternetGateways
- **NAT Gateway**: CreateNatGateway, DeleteNatGateway, DescribeNatGateways
- **Elastic IP**: AllocateAddress, ReleaseAddress, DescribeAddresses, AssociateAddress, DisassociateAddress
- **Route Tables**: CreateRoute, DeleteRoute, CreateRouteTable, DeleteRouteTable, AssociateRouteTable, DisassociateRouteTable, DescribeRouteTables
- **Security Groups**: CreateSecurityGroup, DeleteSecurityGroup, AuthorizeSecurityGroupIngress/Egress, RevokeSecurityGroupIngress/Egress, DescribeSecurityGroups
- **VPC Endpoints**: CreateVpcEndpoint, DeleteVpcEndpoints, DescribeVpcEndpoints, ModifyVpcEndpoint
- **Flow Logs**: CreateFlowLogs, DeleteFlowLogs, DescribeFlowLogs
- **VPC Peering**: CreateVpcPeeringConnection, AcceptVpcPeeringConnection, DeleteVpcPeeringConnection, DescribeVpcPeeringConnections, ModifyVpcPeeringConnectionOptions
- **Network ACLs**: CreateNetworkAcl, DeleteNetworkAcl, ReplaceNetworkAclAssociation, ReplaceNetworkAclEntry, CreateNetworkAclEntry, DeleteNetworkAclEntry, DescribeNetworkAcls
- **Tags**: CreateTags, DeleteTags, DescribeTags
- **General**: DescribeAvailabilityZones, DescribeAccountAttributes

#### NOT Granted (Major ones):

- **EC2 Instances**: RunInstances, TerminateInstances, StartInstances, StopInstances, RebootInstances, DescribeInstances, ModifyInstanceAttribute
- **EBS Volumes**: CreateVolume, DeleteVolume, AttachVolume, DetachVolume, DescribeVolumes, CreateSnapshot, DeleteSnapshot
- **AMIs**: CreateImage, DeregisterImage, DescribeImages, CopyImage, ModifyImageAttribute
- **Key Pairs**: CreateKeyPair, DeleteKeyPair, DescribeKeyPairs, ImportKeyPair
- **Placement Groups**: CreatePlacementGroup, DeletePlacementGroup, DescribePlacementGroups
- **Reserved Instances**: DescribeReservedInstances, ModifyReservedInstances, PurchaseReservedInstancesOffering
- **Spot Instances**: RequestSpotInstances, CancelSpotInstanceRequests, DescribeSpotInstanceRequests
- **VPN**: CreateVpnConnection, DeleteVpnConnection, CreateCustomerGateway, DeleteCustomerGateway
- **Transit Gateway**: CreateTransitGateway, DeleteTransitGateway, AttachTransitGatewayVpcAttachment
- **Network Interfaces**: (Only partial - missing ModifyNetworkInterfaceAttribute, AttachNetworkInterface, DetachNetworkInterface)

### S3 Permissions

#### Currently Granted (26 actions):

- **Bucket Operations**: CreateBucket, DeleteBucket, ListBucket, GetBucketLocation
- **Object Operations**: PutObject, GetObject, DeleteObject, ListBucketVersions, DeleteObjectVersion
- **Bucket Policies**: GetBucketPolicy, PutBucketPolicy, DeleteBucketPolicy
- **Bucket Configuration**:
  - PutBucketVersioning, GetBucketVersioning (implied)
  - PutBucketPublicAccessBlock, GetBucketPublicAccessBlock
  - PutBucketEncryption, GetBucketEncryption
  - PutBucketCORS, GetBucketCORS
  - PutBucketWebsite, GetBucketWebsite, DeleteBucketWebsite
  - PutBucketTagging, GetBucketTagging
  - PutLifecycleConfiguration, GetLifecycleConfiguration
  - PutBucketOwnershipControls, GetBucketOwnershipControls

#### NOT Granted (Major ones):

- **Advanced Object Operations**: CopyObject, RestoreObject, SelectObjectContent, GetObjectTorrent
- **Object ACLs**: GetObjectAcl, PutObjectAcl
- **Bucket ACLs**: GetBucketAcl, PutBucketAcl
- **Bucket Features**:
  - Replication: PutBucketReplication, GetBucketReplication, DeleteBucketReplication
  - Logging: PutBucketLogging, GetBucketLogging
  - Metrics: PutBucketMetricsConfiguration, GetBucketMetricsConfiguration
  - Analytics: PutBucketAnalyticsConfiguration, GetBucketAnalyticsConfiguration
  - Inventory: PutBucketInventoryConfiguration, GetBucketInventoryConfiguration
  - Intelligent Tiering: PutBucketIntelligentTieringConfiguration, GetBucketIntelligentTieringConfiguration
  - Accelerate: PutAccelerateConfiguration, GetAccelerateConfiguration
  - Request Payment: PutBucketRequestPayment, GetBucketRequestPayment
  - Notifications: PutBucketNotificationConfiguration, GetBucketNotificationConfiguration
- **Object Lock**: PutObjectLegalHold, GetObjectLegalHold, PutObjectRetention, GetObjectRetention, PutBucketObjectLockConfiguration
- **Access Points**: CreateAccessPoint, DeleteAccessPoint, GetAccessPoint, ListAccessPoints
- **Multi-Region**: CreateMultiRegionAccessPoint, DeleteMultiRegionAccessPoint, GetMultiRegionAccessPoint
- **Storage Lens**: PutStorageLensConfiguration, GetStorageLensConfiguration
- **Batch Operations**: CreateJob, DescribeJob, ListJobs, UpdateJobPriority, UpdateJobStatus

### Lambda Permissions

#### Currently Granted (24 actions):

- **Function Management**: CreateFunction, DeleteFunction, UpdateFunctionCode, UpdateFunctionConfiguration, GetFunction, GetFunctionConfiguration, ListFunctions
- **Function Execution**: InvokeFunction
- **Permissions**: AddPermission, RemovePermission
- **Tags**: TagResource, UntagResource, ListTags
- **Concurrency**: PutFunctionConcurrency, DeleteFunctionConcurrency
- **Aliases**: CreateAlias, UpdateAlias, DeleteAlias, GetAlias, ListAliases
- **Versions**: PublishVersion, ListVersionsByFunction

#### NOT Granted (Major ones):

- **Layers**: CreateLayer, DeleteLayer, GetLayerVersion, PublishLayerVersion, ListLayers, ListLayerVersions
- **Event Source Mappings**: CreateEventSourceMapping, DeleteEventSourceMapping, GetEventSourceMapping, UpdateEventSourceMapping, ListEventSourceMappings
- **Function URLs**: CreateFunctionUrlConfig, DeleteFunctionUrlConfig, GetFunctionUrlConfig, UpdateFunctionUrlConfig
- **Code Signing**: PutFunctionCodeSigningConfig, GetFunctionCodeSigningConfig, DeleteFunctionCodeSigningConfig
- **Provisioned Concurrency**: PutProvisionedConcurrencyConfig, GetProvisionedConcurrencyConfig, DeleteProvisionedConcurrencyConfig
- **Reserved Concurrency**: PutFunctionReservedConcurrentExecutions, DeleteFunctionReservedConcurrentExecutions
- **Runtime Management**: PutRuntimeManagementConfig, GetRuntimeManagementConfig
- **Async Invocation**: PutFunctionEventInvokeConfig, GetFunctionEventInvokeConfig, DeleteFunctionEventInvokeConfig, ListFunctionEventInvokeConfigs
- **Destinations**: PutDestination, GetDestination, DeleteDestination
- **Account Settings**: GetAccountSettings, UpdateAccountSettings
- **Function State**: GetFunctionConcurrency, ListProvisionedConcurrencyConfigs

### DynamoDB Permissions

#### Currently Granted (20 actions):

- **Table Management**: CreateTable, DeleteTable, DescribeTable, UpdateTable, ListTables (implied)
- **Tags**: TagResource, UntagResource, ListTagsOfResource
- **TTL**: UpdateTimeToLive, DescribeTimeToLive
- **Backups**: CreateBackup, DeleteBackup, ListBackups, DescribeBackup, RestoreTableFromBackup, UpdateContinuousBackups, DescribeContinuousBackups
- **Global Secondary Indexes**: CreateGlobalSecondaryIndex, DeleteGlobalSecondaryIndex, DescribeGlobalSecondaryIndex, UpdateGlobalSecondaryIndex

#### NOT Granted (Major ones):

- **Data Operations**: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGetItem, BatchWriteItem, TransactGetItems, TransactWriteItems, ExecuteStatement, BatchExecuteStatement, ExecuteTransaction
- **Streams**: DescribeStream, GetRecords, GetShardIterator, ListStreams, EnableStreams, DisableStreams
- **Global Tables**: CreateGlobalTable, UpdateGlobalTable, DescribeGlobalTable, ListGlobalTables, UpdateGlobalTableSettings
- **Import/Export**: ImportTable, ExportTableToPointInTime, DescribeImport, DescribeExport
- **PartiQL**: PartiQLDelete, PartiQLInsert, PartiQLSelect, PartiQLUpdate
- **Contributor Insights**: UpdateContributorInsights, DescribeContributorInsights, ListContributorInsights
- **Kinesis Streaming**: EnableKinesisStreamingDestination, DisableKinesisStreamingDestination, DescribeKinesisStreamingDestination
- **Table Class**: UpdateTableReplicaAutoScaling, DescribeTableReplicaAutoScaling

### CloudFront Permissions

#### Currently Granted (18 actions):

- **Distribution Management**: CreateDistribution, UpdateDistribution, DeleteDistribution, GetDistribution, GetDistributionConfig, ListDistributions
- **Tags**: TagResource, UntagResource, ListTagsForResource
- **Invalidations**: CreateInvalidation, GetInvalidation, ListInvalidations
- **Origin Access Control**: CreateOriginAccessControl, GetOriginAccessControl, UpdateOriginAccessControl, DeleteOriginAccessControl, ListOriginAccessControls

#### NOT Granted (Major ones):

- **Origin Access Identity**: CreateCloudFrontOriginAccessIdentity, UpdateCloudFrontOriginAccessIdentity, DeleteCloudFrontOriginAccessIdentity, GetCloudFrontOriginAccessIdentity, ListCloudFrontOriginAccessIdentities
- **Cache Policies**: CreateCachePolicy, UpdateCachePolicy, DeleteCachePolicy, GetCachePolicy, ListCachePolicies
- **Origin Request Policies**: CreateOriginRequestPolicy, UpdateOriginRequestPolicy, DeleteOriginRequestPolicy, GetOriginRequestPolicy, ListOriginRequestPolicies
- **Response Headers Policies**: CreateResponseHeadersPolicy, UpdateResponseHeadersPolicy, DeleteResponseHeadersPolicy, GetResponseHeadersPolicy, ListResponseHeadersPolicies
- **Field Level Encryption**: CreateFieldLevelEncryptionConfig, UpdateFieldLevelEncryptionConfig, DeleteFieldLevelEncryptionConfig, GetFieldLevelEncryption
- **Public Keys**: CreatePublicKey, UpdatePublicKey, DeletePublicKey, GetPublicKey, ListPublicKeys
- **Key Groups**: CreateKeyGroup, UpdateKeyGroup, DeleteKeyGroup, GetKeyGroup, ListKeyGroups
- **Monitoring**: CreateMonitoringSubscription, DeleteMonitoringSubscription, GetMonitoringSubscription
- **Real-time Logs**: CreateRealtimeLogConfig, UpdateRealtimeLogConfig, DeleteRealtimeLogConfig, GetRealtimeLogConfig, ListRealtimeLogConfigs
- **Functions**: CreateFunction, UpdateFunction, DeleteFunction, GetFunction, ListFunctions, PublishFunction, TestFunction
- **Streaming Distributions**: CreateStreamingDistribution, UpdateStreamingDistribution, DeleteStreamingDistribution (deprecated but still exist)

## Recommendations

### Option 1: Use Wildcard Permissions (Simplest)

Instead of listing individual actions, use wildcards for full service access:

```json
{
  "Effect": "Allow",
  "Action": ["ec2:*", "s3:*", "lambda:*", "dynamodb:*", "cloudfront:*"],
  "Resource": "*"
}
```

**Pros**:

- Much smaller policy size
- Automatically includes new permissions as AWS adds them
- Simple to manage

**Cons**:

- Less secure (grants all permissions)
- No fine-grained control
- May grant dangerous permissions like deleting production resources

### Option 2: Group by Function (Recommended)

Create separate policies for different functions:

1. **Infrastructure Policy**: VPC, EC2 networking, CloudFormation
2. **Compute Policy**: Lambda, API Gateway
3. **Storage Policy**: S3, DynamoDB
4. **CDN Policy**: CloudFront, WAF
5. **Monitoring Policy**: CloudWatch, X-Ray

### Option 3: Use AWS Managed Policies

Attach existing AWS managed policies like:

- `PowerUserAccess` (most permissions except IAM)
- `AmazonS3FullAccess`
- `AmazonDynamoDBFullAccess`
- `AWSLambda_FullAccess`
- `CloudFrontFullAccess`

### Option 4: Critical Permissions Only

Focus on the minimum permissions needed for CI/CD:

- Create/update resources
- Read configurations
- Tag resources
- Basic monitoring

Exclude permissions for:

- Data operations (GetItem, PutItem, Query)
- Manual debugging (InvokeFunction)
- Advanced features rarely used in CI/CD
