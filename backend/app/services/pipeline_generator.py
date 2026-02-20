class PipelineGenerator:
    def generate_github_actions(self, project_name: str, branch: str = "main") -> str:
        """
        Generates a standard .github/workflows/deploy.yml
        Includes: Terraform -> Docker -> Trivy -> Kubectl
        """
        return f"""name: Deploy {project_name}

on:
  push:
    branches: [ "{branch}" ]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: {project_name}
  EKS_CLUSTER_NAME: phoenix-cluster-01

jobs:
  deploy:
    name: Build & Deploy
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
    - name: Checkout Code
      uses: actions/checkout@v3

    - name: Configure AWS Credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-region: ${{{{ env.AWS_REGION }}}}

    # 1. Infrastructure (Terraform)
    - name: Terraform Init & Apply
      run: |
        cd infra
        terraform init
        terraform apply -auto-approve

    # 2. Build & Push (Docker)
    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v1

    - name: Build, Tag, and Push Image
      env:
        ECR_REGISTRY: ${{{{ steps.login-ecr.outputs.registry }}}}
        IMAGE_TAG: ${{{{ github.sha }}}}
      run: |
        docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

    # 3. Security Scan (Trivy)
    - name: Run Trivy Vulnerability Scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: '${{{{ steps.login-ecr.outputs.registry }}}}/${{{{ env.ECR_REPOSITORY }}}}:${{{{ github.sha }}}}'
        format: 'table'
        exit-code: '1'
        ignore-unfixed: true
        severity: 'CRITICAL,HIGH'

    # 4. Deploy (Kubernetes)
    - name: Update Kubeconfig
      run: aws eks update-kubeconfig --name ${{{{ env.EKS_CLUSTER_NAME }}}} --region ${{{{ env.AWS_REGION }}}}

    - name: Deploy to EKS
      run: |
        cd k8s
        # Replace image placeholder with actual image
        sed -i "s|IMAGE_PLACEHOLDER|${{{{ steps.login-ecr.outputs.registry }}}}/${{{{ env.ECR_REPOSITORY }}}}:${{{{ github.sha }}}}|g" deployment.yaml
        kubectl apply -f .
"""