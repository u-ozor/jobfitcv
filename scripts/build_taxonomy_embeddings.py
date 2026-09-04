#scripts/build_taxonomy_embeddings
#
# Targeting a field outside security/IT? Edit the TAXONOMIES dict below —
# add your own track name -> a keyword-dense description of that track
# (skills, tools, role names a JD in that field would use), then re-run
# this script. It classifies incoming job postings by cosine similarity
# against these descriptions, so the description needs to sit at the
# semantic centroid of the track, not just its most distinctive terms —
# generic-sounding words like "monitoring" or "infrastructure" still belong
# in the description if they're actually common in that field's postings,
# otherwise a track can lose real postings to a neighboring track that
# happens to share those generic terms.
# Prefer a guided flow instead? Run scripts/taxonomy_builder.py — same
# embed+save mechanism, interactive prompts, doesn't require editing this file.

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # allow direct invocation

import numpy as np

from app.core.embedder import embed_text


TAXONOMIES = {
    "soc_security":
        "SOC analyst SIEM Splunk Wazuh ELK monitoring incident response threat hunting phishing detection log analysis malware triage EDR endpoint detection response SOAR indicators of compromise threat intelligence CVE vulnerability alert triage",

    "backend_api":
        "Backend API development FastAPI Django Flask Python microservices REST JSON authentication JWT PostgreSQL SQL ORM database server-side web services scalability",

    "it_support":
        "IT support helpdesk Tier 1 troubleshooting ticketing Jira ServiceNow ITIL customer support systems endpoint management desktop support hardware software installation user onboarding SLA",

    "cloud_devops":
        "AWS GCP Azure cloud platform EC2 S3 Lambda ECS EKS Kubernetes Docker container orchestration Terraform Pulumi CloudFormation infrastructure as code GitHub Actions GitLab CI Jenkins ArgoCD GitOps CI CD pipeline serverless blue-green deployment cloud-native SRE Prometheus Grafana Datadog CloudWatch cost optimization IAM secrets management cloud security posture",

    "sysadmin_itops":
        "System administrator Linux Windows server administration patch management server builds rack install physical virtual server maintenance disaster recovery backup restore SAN NAS storage VMware Hyper-V Proxmox Active Directory Group Policy Microsoft 365 Entra ID Exchange Online multi-site infrastructure on-premise change management capacity planning SNMP Nagios Zabbix PRTG server hardening firewall DNS DHCP VPN network switches VLANs on-call escalation ITIL change control",

    "ai_ml":
        "machine learning deep learning neural networks NLP large language models LLM fine-tuning embeddings vector database RAG retrieval augmented generation AI engineer ML engineer data science Python PyTorch TensorFlow scikit-learn Hugging Face transformers model training inference pipeline MLOps AI product generative AI agent AI application"
}


for name, text in TAXONOMIES.items():

    embedding = embed_text(text)

    np.save(
        f"data/taxonomy/{name}.npy",
        embedding
    )

    print("Built:", name)