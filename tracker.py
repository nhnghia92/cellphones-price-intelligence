        min_change_raw = os.getenv(
            "MIN_CHANGE_PCT",
            "5"
        )

        try:
            min_change = (
                float(min_change_raw)
                if min_change_raw.strip()
                else 5.0
            )
        except ValueError:
            min_change = 5.0

        if (
            change_1d is not None
            and abs(change_1d) >= min_change
        ):
            events.append([
                now.isoformat(),
                product_id,
                "",
                "",
                (
                    "PRICE_DROP"
                    if change_1d < 0
                    else "PRICE_INCREASE"
                ),
                change_1d,
                (
                    "HIGH"
                    if abs(change_1d) >= 10
                    else "MEDIUM"
                ),
                f"{previous_price:,.0f} -> "
                f"{current_price:,.0f}",
            ])
