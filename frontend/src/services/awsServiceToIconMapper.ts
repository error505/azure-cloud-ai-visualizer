// Mapping of common AWS service name variants to AWS architecture icon titles
// The icon titles correspond to filenames in public/aws_icons (without size/extension)
export const AWS_SERVICE_TO_ICON_MAPPINGS: { [key: string]: string } = {
  // Compute
  'ec2': 'Arch_Amazon-EC2',
  'amazon ec2': 'Arch_Amazon-EC2',
  'aws ec2': 'Arch_Amazon-EC2',
  'elastic compute': 'Arch_Amazon-EC2',

  'lambda': 'Arch_AWS-Lambda',
  'aws lambda': 'Arch_AWS-Lambda',
  'amazon lambda': 'Arch_AWS-Lambda',

  'lightsail': 'Arch_Amazon-Lightsail',
  'aws lightsail': 'Arch_Amazon-Lightsail',

  'batch': 'Arch_AWS-Batch',

  // Containers / Orchestration
  'ecs': 'Arch_AWS-ECS',
  'aws ecs': 'Arch_AWS-ECS',
  'amazon ecs': 'Arch_AWS-ECS',

  'eks': 'Arch_Amazon-EKS',
  'aws eks': 'Arch_Amazon-EKS',
  'amazon eks': 'Arch_Amazon-EKS',

  'ecr': 'Arch_AWS-Elastic-Container-Registry',
  'aws ecr': 'Arch_AWS-Elastic-Container-Registry',

  // Storage
  's3': 'Arch_Amazon-S3',
  'amazon s3': 'Arch_Amazon-S3',
  's3 bucket': 'Arch_Amazon-S3',

  'ebs': 'Arch_Amazon-EBS',
  'efs': 'Arch_Amazon-EFS',

  // Database
  'rds': 'Arch_Amazon-RDS',
  'amazon rds': 'Arch_Amazon-RDS',
  'relational database': 'Arch_Amazon-RDS',

  'dynamodb': 'Arch_Amazon-DynamoDB',
  'amazon dynamodb': 'Arch_Amazon-DynamoDB',

  'redshift': 'Arch_Amazon-Redshift',
  'amazon redshift': 'Arch_Amazon-Redshift',

  'elasticache': 'Arch_Amazon-ElastiCache',
  'amazon elasticache': 'Arch_Amazon-ElastiCache',

  'neptune': 'Arch_Amazon-Neptune',

  // Networking
  'vpc': 'Arch_Amazon-VPC',
  'virtual private cloud': 'Arch_Amazon-VPC',
  'amazon vpc': 'Arch_Amazon-VPC',

  'subnet': 'Arch_Amazon-Subnet',
  'route53': 'Arch_Amazon-Route-53',
  'route 53': 'Arch_Amazon-Route-53',
  'route53 dns': 'Arch_Amazon-Route-53',

  'cloudfront': 'Arch_Amazon-CloudFront',
  'cdn': 'Arch_Amazon-CloudFront',

  'elb': 'Arch_Amazon-ELB',
  'elastic load balancer': 'Arch_Amazon-ELB',
  'application load balancer': 'Arch_Amazon-ALB',
  'alb': 'Arch_Amazon-ALB',

  'network load balancer': 'Arch_Amazon-NLB',
  'nlb': 'Arch_Amazon-NLB',

  // Messaging
  'sqs': 'Arch_Amazon-SQS',
  'sns': 'Arch_Amazon-SNS',

  // Identity & Security
  'iam': 'Arch_AWS-IAM',
  'identity and access management': 'Arch_AWS-IAM',

  'kms': 'Arch_AWS-KMS',
  'secrets manager': 'Arch_AWS-Secrets-Manager',
  'aws secrets manager': 'Arch_AWS-Secrets-Manager',

  'waf': 'Arch_AWS-WAF',

  // Monitoring & Observability
  'cloudwatch': 'Arch_Amazon-CloudWatch',
  'aws cloudwatch': 'Arch_Amazon-CloudWatch',

  // Analytics / Streaming
  'kinesis': 'Arch_Amazon-Kinesis',
  'kinesis data streams': 'Arch_Amazon-Kinesis',

  'athena': 'Arch_Amazon-Athena',
  'glue': 'Arch_AWS-Glue',

  // Integration / API
  'api gateway': 'Arch_Amazon-API-Gateway',
  'aws api gateway': 'Arch_Amazon-API-Gateway',

  // Developer tools / management
  'cloudformation': 'Arch_AWS-CloudFormation',
  'cloudformation stack': 'Arch_AWS-CloudFormation',

  // ML / AI
  'sagemaker': 'Arch_Amazon-SageMaker',
  'amazon sagemaker': 'Arch_Amazon-SageMaker',

  // Other / generic
  'mq': 'Arch_Amazon-MQ',
  'step functions': 'Arch_AWS-Step-Functions',
  'cognito': 'Arch_Amazon-Cognito',
  'api management': 'Arch_Amazon-API-Gateway',
  'amplify': 'Arch_AWS-Amplify',
  'aws amplify': 'Arch_AWS-Amplify',
  'amazon amplify': 'Arch_AWS-Amplify',
  'amazon textract': 'Arch_Amazon-Textract',
  'textract': 'Arch_Amazon-Textract',
  'amazon rekognition': 'Arch_Amazon-Rekognition',
  'rekognition': 'Arch_Amazon-Rekognition',
  'amazon translate': 'Arch_Amazon-Translate',
  'translate': 'Arch_Amazon-Translate',
  'amazon polly': 'Arch_Amazon-Polly',
  'polly': 'Arch_Amazon-Polly',
  'amazon comprehend': 'Arch_Amazon-Comprehend',
  'comprehend': 'Arch_Amazon-Comprehend',
};

export default AWS_SERVICE_TO_ICON_MAPPINGS;
