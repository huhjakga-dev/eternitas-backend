up:
	docker compose up -d
	docker compose -f docker-compose.dashboard.yaml up -d

down:
	docker compose -f docker-compose.dashboard.yaml down
	docker compose down

restart:
	$(MAKE) down
	$(MAKE) up

logs:
	docker compose logs -f &
	docker compose -f docker-compose.dashboard.yaml logs -f
