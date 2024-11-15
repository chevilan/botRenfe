from renfTools import *
import argparse

def form_abono():
    parser = argparse.ArgumentParser(description="Bot buscador de tren en abono")
    parser.add_argument('-debug', action='store_true', help='Activar modo debug')
    args = parser.parse_args()
    main=tools(True,debug=args.debug)
    main.log_in()
    main.new_formal()
    main.select_travel(True)
    main.print_trains_select()
    main.coger_tren(True)
    main.confirmar_venta()
    main.close()
    
if __name__=='__main__':
    try:
        form_abono()
    except KeyboardInterrupt:
        print("\n\nSaliendo de forzosamente...")
    except Exception as e:
        print(f"Error: {e}")