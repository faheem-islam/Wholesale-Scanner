"""Wholesaler adapters — one module per site, each implementing the shared
WholesalerAdapter interface in base.py. Adding a new wholesaler means
writing one new adapter file and registering it in main.py's ADAPTERS
dict; it should not require touching any other adapter.
"""
