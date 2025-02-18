'''
Fake TCP Client
'''

from sys import argv

from fake_tcp import Client


def main():
    try:
        filename = argv[1]
        server_ip = argv[2]
        server_port = int(argv[3])
    except Exception:
        print("3 arguments required: filename server_ip server_port")
        return
        
    client = Client(server_ip=server_ip, server_port=server_port)
    client.send(filename)
    
    

if __name__ == '__main__':
    main()
