"""Alert logging command for Turtle Trading system.

This command logs alerts and manages open position snapshots
for the website dashboard.
"""

from datetime import datetime
from decimal import Decimal

from src.domain.interfaces.repositories import AlertRepository, OpenPositionRepository
from src.domain.models.alert import Alert, AlertType, OpenPositionSnapshot
from src.domain.models.enums import Direction, System

# Thresholds for significant change detection
PRICE_CHANGE_THRESHOLD = Decimal("0.005")  # 0.5%
PNL_CHANGE_THRESHOLD = Decimal("50")  # $50


def is_significant_change(
    current: OpenPositionSnapshot,
    new_price: Decimal,
    new_pnl: Decimal,
    new_stop: Decimal | None = None,
) -> bool:
    """Determine if position change warrants a DB write.

    A change is significant if any of these conditions are met:
    - Price moved more than 0.5%
    - P&L changed by more than $50
    - Stop price changed (pyramid happened)

    Args:
        current: Current position snapshot
        new_price: New current price
        new_pnl: New unrealized P&L
        new_stop: New stop price (if changed)

    Returns:
        True if change is significant and should be persisted
    """
    # Price moved more than 0.5%
    if current.current_price:
        price_change = abs(new_price - current.current_price) / current.current_price
        if price_change > PRICE_CHANGE_THRESHOLD:
            return True

    # P&L changed by more than $50
    if current.unrealized_pnl is not None:
        if abs(new_pnl - current.unrealized_pnl) > PNL_CHANGE_THRESHOLD:
            return True

    # Stop price changed (pyramid happened)
    if new_stop and current.stop_price:
        if new_stop != current.stop_price:
            return True

    return False


class AlertLogger:
    """Command to log alerts and manage position snapshots.

    This command:
    1. Creates alert records for trading events
    2. Manages open_positions table for dashboard display
    3. Coordinates alert + position writes for consistency
    """

    def __init__(
        self,
        alert_repo: AlertRepository,
        position_repo: OpenPositionRepository,
    ) -> None:
        """Initialize the alert logger.

        Args:
            alert_repo: Repository for alert persistence
            position_repo: Repository for position snapshots
        """
        self._alert_repo = alert_repo
        self._position_repo = position_repo

    async def log_signal(
        self,
        symbol: str,
        direction: Direction,
        system: System,
        price: Decimal,
        details: dict | None = None,
    ) -> Alert:
        """Log an entry signal detection.

        Args:
            symbol: Market symbol
            direction: Trade direction
            system: S1 or S2
            price: Signal price
            details: Additional signal details

        Returns:
            Created Alert
        """
        alert = Alert(
            symbol=symbol,
            alert_type=AlertType.ENTRY_SIGNAL,
            direction=direction,
            system=system,
            price=price,
            details=details or {},
        )
        await self._alert_repo.save(alert)
        return alert

    async def log_position_opened(
        self,
        symbol: str,
        direction: Direction,
        system: System,
        entry_price: Decimal,
        contracts: int,
        stop_price: Decimal,
        n_value: Decimal,
    ) -> Alert:
        """Log a position being opened.

        Creates both an alert and an open_positions snapshot.

        Args:
            symbol: Market symbol
            direction: Trade direction
            system: S1 or S2
            entry_price: Entry fill price
            contracts: Number of contracts/shares
            stop_price: Initial stop price
            n_value: N (ATR) at entry

        Returns:
            Created Alert
        """
        now = datetime.now()

        # Create alert
        alert = Alert(
            symbol=symbol,
            alert_type=AlertType.POSITION_OPENED,
            direction=direction,
            system=system,
            price=entry_price,
            details={
                "contracts": contracts,
                "stop_price": float(stop_price),
                "n_value": float(n_value),
            },
        )
        await self._alert_repo.save(alert)

        # Create position snapshot
        snapshot = OpenPositionSnapshot(
            symbol=symbol,
            direction=direction,
            system=system,
            entry_price=entry_price,
            entry_date=now,
            contracts=contracts,
            units=1,
            current_price=entry_price,
            stop_price=stop_price,
            unrealized_pnl=Decimal("0"),
            n_value=n_value,
            updated_at=now,
        )
        await self._position_repo.upsert(snapshot)

        return alert

    async def log_exit(
        self,
        symbol: str,
        alert_type: AlertType,
        exit_price: Decimal,
        details: dict | None = None,
    ) -> Alert:
        """Log a position exit.

        Creates alert and deletes position snapshot.

        Args:
            symbol: Market symbol
            alert_type: EXIT_STOP or EXIT_BREAKOUT
            exit_price: Exit fill price
            details: Additional details (reason, pnl, etc.)

        Returns:
            Created Alert
        """
        alert = Alert(
            symbol=symbol,
            alert_type=alert_type,
            price=exit_price,
            details=details or {},
        )
        await self._alert_repo.save(alert)

        # Delete position snapshot
        await self._position_repo.delete(symbol)

        return alert

    async def log_pyramid(
        self,
        symbol: str,
        trigger_price: Decimal,
        new_units: int,
        new_stop: Decimal,
        new_contracts: int,
    ) -> Alert:
        """Log a pyramid being added.

        Creates alert and updates position snapshot.

        Args:
            symbol: Market symbol
            trigger_price: Price that triggered pyramid
            new_units: Total units after pyramid
            new_stop: New stop price after pyramid
            new_contracts: Total contracts after pyramid

        Returns:
            Created Alert
        """
        alert = Alert(
            symbol=symbol,
            alert_type=AlertType.PYRAMID_TRIGGER,
            price=trigger_price,
            details={
                "new_units": new_units,
                "new_stop": float(new_stop),
                "new_contracts": new_contracts,
            },
        )
        await self._alert_repo.save(alert)

        # Update position snapshot
        existing = await self._position_repo.get(symbol)
        if existing:
            updated = OpenPositionSnapshot(
                symbol=existing.symbol,
                direction=existing.direction,
                system=existing.system,
                entry_price=existing.entry_price,
                entry_date=existing.entry_date,
                contracts=new_contracts,
                units=new_units,
                current_price=trigger_price,
                stop_price=new_stop,
                unrealized_pnl=existing.unrealized_pnl,
                n_value=existing.n_value,
                updated_at=datetime.now(),
            )
            await self._position_repo.upsert(updated)

        return alert

    async def update_position(self, snapshot: OpenPositionSnapshot) -> None:
        """Update position snapshot without creating alert.

        Used for significant price/P&L changes between actions.

        Args:
            snapshot: Updated position snapshot
        """
        await self._position_repo.upsert(snapshot)
