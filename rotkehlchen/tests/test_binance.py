import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from rotkehlchen.binance import Binance, trade_from_binance
from rotkehlchen.errors import RemoteError
from rotkehlchen.fval import FVal
from rotkehlchen.order_formatting import Trade


@pytest.fixture
def mock_binance(accounting_data_dir, inquirer):
    binance = Binance(b'', b'', inquirer, accounting_data_dir)
    this_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = Path(this_dir).parent / 'tests' / 'utils' / 'data' / 'binance_exchange_info.json'
    with json_path.open('r') as f:
        json_data = json.loads(f.read())

    binance._populate_symbols_to_pair(json_data)
    binance.first_connection_made = True
    return binance


def test_trade_from_binance(mock_binance):
    binance_trades_list = [
        {
            'symbol': 'RDNETH',
            'id': 1,
            'orderId': 1,
            'price': FVal(0.0063213),
            'qty': FVal(5.0),
            'commission': FVal(0.005),
            'commissionAsset': 'RDN',
            'time': 1512561941,
            'isBuyer': True,
            'isMaker': False,
            'isBestMatch': True,
        }, {
            'symbol': 'ETHUSDT',
            'id': 1,
            'orderId': 1,
            'price': FVal(481.0),
            'qty': FVal(0.505),
            'commission': FVal(0.242905),
            'commissionAsset': 'USDT',
            'time': 1531117990,
            'isBuyer': False,
            'isMaker': True,
            'isBestMatch': True,
        }, {
            'symbol': 'BTCUSDT',
            'id': 1,
            'orderId': 1,
            'price': FVal(6376.39),
            'qty': FVal(0.051942),
            'commission': FVal(0.00005194),
            'commissionAsset': 'BTC',
            'time': 1531728338,
            'isBuyer': True,
            'isMaker': False,
            'isBestMatch': True,
        }, {
            'symbol': 'ADAUSDT',
            'id': 1,
            'orderId': 1,
            'price': FVal(0.17442),
            'qty': FVal(285.2),
            'commission': FVal(0.00180015),
            'commissionAsset': 'BNB',
            'time': 1531871806,
            'isBuyer': False,
            'isMaker': True,
            'isBestMatch': True,
        },
    ]
    our_expected_list = [
        Trade(
            timestamp=1512561941,
            pair='RDN_ETH',
            type='buy',
            rate=FVal(0.0063213),
            cost=FVal(0.03160650),
            cost_currency='ETH',
            fee=FVal(0.005),
            fee_currency='RDN',
            amount=FVal(5.0),
            location='binance',
        ),
        Trade(
            timestamp=1531117990,
            pair='ETH_USDT',
            type='sell',
            rate=FVal(481.0),
            cost=FVal(242.905),
            cost_currency='USDT',
            fee=FVal(0.242905),
            fee_currency='USDT',
            amount=FVal(0.505),
            location='binance',
        ),
        Trade(
            timestamp=1531728338,
            pair='BTC_USDT',
            type='buy',
            rate=FVal(6376.39),
            cost=FVal(331.20244938),
            cost_currency='USDT',
            fee=FVal(0.00005194),
            fee_currency='BTC',
            amount=FVal(0.051942),
            location='binance',
        ),
        Trade(
            timestamp=1531871806,
            pair='ADA_USDT',
            type='sell',
            rate=FVal(0.17442),
            cost=FVal(49.744584),
            cost_currency='USDT',
            fee=FVal(0.00180015),
            fee_currency='BNB',
            amount=FVal(285.2),
            location='binance',
        ),
    ]

    for idx, binance_trade in enumerate(binance_trades_list):
        our_trade = trade_from_binance(binance_trade, mock_binance.symbols_to_pair)
        assert our_trade == our_expected_list[idx]


exchange_info_mock_text = '''{
  "timezone": "UTC",
  "serverTime": 1508631584636,
  "symbols": [{
    "symbol": "ETHBTC",
    "status": "TRADING",
    "baseAsset": "ETH",
    "baseAssetPrecision": 8,
    "quoteAsset": "BTC",
    "quotePrecision": 8,
    "icebergAllowed": false
    }]
}'''


def test_binance_backoff_after_429(mock_binance):
    class MockResponse():

        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text
            self.url = 'http://someurl.com'

    count = 0

    def mock_429(url):
        nonlocal count
        if count < 2:
            response = MockResponse(429, '{"code": -1103, "msg": "Too many requests"}')
        else:
            response = MockResponse(200, exchange_info_mock_text)
        count += 1
        return response

    mock_binance.initial_backoff = 0.5
    mock_binance.backoff_limit = 2
    with patch.object(mock_binance.session, 'get', side_effect=mock_429):
        # test that after 2 429 cals we finally succeed in the API call
        result = mock_binance.api_query('exchangeInfo')
        assert 'timezone' in result

        # Test the backoff_limit properly returns an error when hit
        count = -9999999
        with pytest.raises(RemoteError):
            mock_binance.api_query('exchangeInfo')
