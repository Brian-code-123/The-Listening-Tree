#!/bin/bash
#
# setup-vercel.sh — Automated Vercel Deployment Setup
# 
# This script automates the environment variable configuration for Vercel deployment.
# It requires:
#   1. Vercel CLI installed (brew install vercel)
#   2. User authenticated with Vercel (vercel whoami)
#   3. DATABASE_URL environment variable (see DATABASE_URL_EXAMPLES below)
#
# Usage:
#   bash scripts/setup-vercel.sh
#
# Or with custom DATABASE_URL:
#   DATABASE_URL="postgresql://..." bash scripts/setup-vercel.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  🚀 The Listening Tree — Vercel Setup Automation   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo

# Step 1: Verify Vercel CLI
echo -e "${YELLOW}[1/4] Checking Vercel CLI...${NC}"
if ! command -v vercel &> /dev/null; then
    echo -e "${RED}❌ Vercel CLI not found. Install with: brew install vercel${NC}"
    exit 1
fi
VERCEL_VERSION=$(vercel --version 2>/dev/null || echo "unknown")
echo -e "${GREEN}✅ Vercel CLI found: $VERCEL_VERSION${NC}"
echo

# Step 2: Verify authentication
echo -e "${YELLOW}[2/4] Verifying Vercel authentication...${NC}"
AUTH=$(vercel whoami 2>&1)
if [[ $AUTH == *"Error"* ]] || [[ -z "$AUTH" ]]; then
    echo -e "${RED}❌ Not authenticated with Vercel. Run: vercel login${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Authenticated as: $AUTH${NC}"
echo

# Step 3: Load environment variables
echo -e "${YELLOW}[3/4] Loading environment variables...${NC}"
PROJECT_DIR=$(pwd)
ENV_FILE="${PROJECT_DIR}/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ .env file not found. Please create it first.${NC}"
    exit 1
fi

# Source .env (safely)
export $(cat "$ENV_FILE" | grep -v '^#' | grep -v '^$' | xargs)

# Validate required variables
REQUIRED_VARS=("ZHIPU_API_KEY" "SECRET_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}❌ Missing required variables in .env: ${MISSING_VARS[*]}${NC}"
    echo "Please add these to .env and try again."
    exit 1
fi

echo -e "${GREEN}✅ Environment variables loaded:${NC}"
echo "   • ZHIPU_API_KEY: $(echo $ZHIPU_API_KEY | cut -c1-20)..."
echo "   • SECRET_KEY: $(echo $SECRET_KEY | cut -c1-20)..."

# Check DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}⚠️  DATABASE_URL not set in .env${NC}"
    echo
    echo -e "${BLUE}DATABASE_URL Examples:${NC}"
    echo -e "  ${YELLOW}For Supabase (Recommended):${NC}"
    echo "  postgresql://postgres.XXXXX:password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
    echo
    echo -e "  ${YELLOW}For Neon PostgreSQL:${NC}"
    echo "  postgresql://user:password@ep-XXXXX.ng.neon.tech:5432/thelisteningtree?sslmode=require"
    echo
    echo -e "  ${YELLOW}For Railway:${NC}"
    echo "  postgresql://user:password@rail.proxy.rlwy.net:XXXX/railway"
    echo
    echo -e "  ${YELLOW}⚠️  For local development only (do NOT use in production):${NC}"
    echo "  reminders.db"
    echo
    read -p "Enter your DATABASE_URL (or press Enter to skip): " DATABASE_URL_INPUT
    if [ ! -z "$DATABASE_URL_INPUT" ]; then
        DATABASE_URL="$DATABASE_URL_INPUT"
    fi
else
    echo "   • DATABASE_URL: $(echo $DATABASE_URL | cut -c1-30)..."
fi

echo
echo -e "${YELLOW}[4/4] Linking project and setting environment variables...${NC}"

# Note: This requires manual interaction with Vercel CLI
# We'll guide the user through the process

echo -e "${BLUE}Next steps:${NC}"
echo
echo "1. Create or use existing Vercel project:"
echo "   ${YELLOW}vercel link --project the-listening-tree${NC}"
echo
echo "2. Set environment variables for Production:"
echo "   ${YELLOW}vercel env add ZHIPU_API_KEY${NC}"
echo "   ${YELLOW}vercel env add SECRET_KEY${NC}"
if [ ! -z "$DATABASE_URL" ]; then
    echo "   ${YELLOW}vercel env add DATABASE_URL${NC}"
fi
echo
echo "3. Verify environment variables:"
echo "   ${YELLOW}vercel env list${NC}"
echo
echo "4. Deploy to Vercel:"
echo "   ${YELLOW}git push${NC}"
echo "   (Automatic deployment via GitHub integration)"
echo "   Or manually:"
echo "   ${YELLOW}vercel --prod${NC}"
echo
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "For detailed instructions, see: VERCEL_DEPLOYMENT.md"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
