# Smoker Controller Makefile

.PHONY: help dev build install test clean

help: ## Show this help message
	@echo "Smoker Controller - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Start development servers (backend + frontend)
	@echo "Starting development servers..."
	@echo "Backend will run on http://localhost:8000"
	@echo "Frontend will run on http://localhost:5173"
	@echo ""
	@echo "Starting backend..."
	@cd backend && poetry run uvicorn app:app --host 0.0.0.0 --port 8000 --reload &
	@echo "Starting frontend..."
	@cd frontend && npm run dev &
	@echo ""
	@echo "Development servers started!"
	@echo "Press Ctrl+C to stop all servers"

build: ## Build frontend for production
	@echo "Building frontend..."
	@cd frontend && npm run build
	@echo "Frontend built successfully!"

install: ## Install system dependencies and setup
	@echo "Installing system dependencies..."
	@sudo apt-get update
	@sudo apt-get install -y python3-pip python3-venv
	@echo "Installing Python dependencies..."
	@cd backend && poetry install
	@echo "Installing Node.js dependencies..."
	@cd frontend && npm install
	@echo "Setup complete!"

service-install: ## Install systemd service
	@echo "Installing systemd service..."
	@sudo cp backend/smoker.service /etc/systemd/system/
	@sudo systemctl daemon-reload
	@sudo systemctl enable smoker
	@echo "Service installed! Use 'sudo systemctl start smoker' to start"

service-start: ## Start the systemd service
	@sudo systemctl start smoker
	@echo "Service started!"

service-stop: ## Stop the systemd service
	@sudo systemctl stop smoker
	@echo "Service stopped!"

service-status: ## Check service status
	@sudo systemctl status smoker

service-logs: ## View service logs
	@sudo journalctl -u smoker -f

test: ## Run tests
	@echo "Running backend tests..."
	@cd backend && poetry run pytest
	@echo "Running frontend tests..."
	@cd frontend && npm run test

clean: ## Clean build artifacts
	@echo "Cleaning build artifacts..."
	@rm -rf frontend/dist
	@rm -rf backend/__pycache__
	@rm -rf backend/*/__pycache__
	@find . -name "*.pyc" -delete
	@echo "Clean complete!"

setup-pi: ## Setup Raspberry Pi for smoker controller
	@echo "Setting up Raspberry Pi..."
	@echo "1. Enable SPI interface:"
	@echo "   sudo raspi-config -> Interface Options -> SPI -> Enable"
	@echo "2. Install system dependencies:"
	@echo "   sudo apt-get update"
	@echo "   sudo apt-get install -y python3-pip python3-venv git"
	@echo "3. Install Node.js:"
	@echo "   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -"
	@echo "   sudo apt-get install -y nodejs"
	@echo "4. Run 'make install' to install dependencies"
	@echo "5. Run 'make service-install' to install systemd service"
	@echo "6. Configure .env file in /etc/smoker.env"
	@echo "7. Run 'make service-start' to start the service"

production-build: build ## Build for production deployment
	@echo "Production build complete!"
	@echo "Frontend built to frontend/dist/"
	@echo "Backend ready for deployment"

production-deploy: production-build ## Deploy to production
	@echo "Deploying to production..."
	@sudo mkdir -p /opt/smoker
	@sudo cp -r backend /opt/smoker/
	@sudo cp -r frontend/dist /opt/smoker/frontend/
	@sudo chown -R pi:pi /opt/smoker
	@echo "Deployment complete!"
	@echo "Run 'make service-start' to start the service"
