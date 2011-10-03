#!/usr/bin/python
# vim: et ts=4 :
import sys
import re


class ParseRedback(object):
    """
    """
    def __init__(self, cfg):


        self.configuration = {}
        
        self.configfile = cfg       
        self._getContextConfig(self.configfile) 
        self._parseContextConfig()
        self.parsePort(self.configfile)
    
    
    def _getContextConfig(self, cfg):
        """ Parse config and store contextconfig and RD
        """
        self.fh = open(cfg,"r")
        self.config = self.fh.readlines()
        self.current_context = None
        self.text = None
        
        for line in self.config:
            m = re.match('^context\s(?P<context_name>[a-zA-Z0-9_:\-&\/]+)?(\svpn-rd\s.*:(?P<vpn_rd>[0-9]+))?', line, re.VERBOSE)
            n = re.match('.*(^!\s\*\*\sEnd\sContext\s\*\*)', line, re.VERBOSE)
            if (n is not None):
                self.configuration[self.current_context]['raw_config'] = self.text
            elif (m is not None):
                if(self.current_context):
                    self.configuration[self.current_context]['raw_config'] = self.text
                self.current_context = m.group('context_name')
                if self.current_context is None:
                    print "ERRORRR context fuckedup ->", self.line
                    exit()
                self.configuration[self.current_context] = {}
                self.configuration[self.current_context]['vpn_rd'] = m.group('vpn_rd') 
                self.text = line 
            elif not re.match("^!", line, re.VERBOSE):
                if(self.current_context):
                    self.text += line

    

    def _parseContextConfig(self):
        """ Parse config and find useful stuff
        """
        
        self.parent_intf = None
        self.bgp_peer_address = None
        import radix
        
        for self.current_context in self.configuration:
            self.config = self.configuration[self.current_context]['raw_config'].split('\n')
            self.configuration[self.current_context]['interface'] = {}
            interface= self.configuration[self.current_context]['interface']
            self.configuration[self.current_context]['routing'] = {}
            self.configuration[self.current_context]['routing']['connected'] = radix.Radix()
            connected = self.configuration[self.current_context]['routing']['connected']
        
        
            #find interfaces and attributes for them
            for line in self.config:
                #interface
                if re.match('\sinterface', line, re.VERBOSE):
                    if re.match('GE', line.split()[1], re.VERBOSE):
                        self.parent_intf = line.split()[1]
                        interface[self.parent_intf] = {}
                        if len(self.parent_intf.split('.')) == 2:
                            interface[self.parent_intf]['vlan_id'] = self.parent_intf.split('.')[1]
                elif (self.parent_intf) and (len(line) - len(line.lstrip())) == 2:
                    ##description
                    if line.lstrip().startswith('description'):
                        interface[self.parent_intf]['description'] = line.lstrip('  description') 
                    #ip address pri+sec
                    if line.lstrip().startswith('ip address'):
                        #primary
                        if not 'pri_ipv4' in interface[self.parent_intf]:
                            self.ip_address = line.lstrip('  ip address')
                            interface[self.parent_intf]['pri_ipv4'] = self.ip_address
                        #first secondary
                        elif not 'sec_ipv4' in interface[self.parent_intf]:
                            self.ip_address = line.lstrip('  ip address').rstrip(' secondary')
                            interface[self.parent_intf]['sec_ipv4'] = [self.ip_address]
                        #another secondary
                        else:
                            self.ip_address = line.lstrip('  ip address').rstrip(' secondary')
                            interface[self.parent_intf]['sec_ipv4'].append(self.ip_address)
                        rnode = connected.add(self.ip_address)
                        rnode.data['parent_intf'] = self.parent_intf
                    #ip-helper
                    if line.lstrip().startswith('dhcp relay'):
                        interface[self.parent_intf]['dhcp_relay'] = True
                else:
                    self.parent_intf = None
                
                #static routing
                if re.match('\sip\sroute', line, re.VERBOSE):
                    self.route_line = line.split()
                    #first route
                    if not 'static' in  self.configuration[self.current_context]['routing']:
                        self.configuration[self.current_context]['routing']['static'] = {}
                        static  = self.configuration[self.current_context]['routing']['static'] 
                    
                    static[self.route_line[2]] = {}
                    
                    if self.route_line[3] == "context":
                        static[self.route_line[2]]['nexthop'] = None
                    elif self.route_line[3] == "null0":
                        static[self.route_line[2]]['nexthop'] = None
                    elif len(self.route_line[3].split('.')) != 4:
                        #nexthop is a interface?
                        static[self.route_line[2]]['oif'] = self.route_line[3]
                    else:
                        #Look if nexthop is in our connected dict
                        rnode = self.configuration[self.current_context]['routing']['connected'].search_best(self.route_line[3])
                        if rnode is not None:
                            parent_intf = rnode.data['parent_intf']
                            static[self.route_line[2]]['nexthop'] = self.route_line[3]
                            #print self.route_line[2] + " -> " + self.route_line[3] + " (" + parent_intf + ")"
                        else:
                            #remove the prefix
                            static.pop(self.route_line[2])
                            #print "ROUTE NOT IN CONNECTED:", self.route_line[2], self.route_line[3]
                
                #DHCP relay
                if re.match('\sdhcp\srelay\sserver', line, re.VERBOSE):
                    self.dhcp_line = line.split()
                    if not 'dhcp_relay' in self.configuration[self.current_context]:
                        self.configuration[self.current_context]['dhcp_relay'] = {}
                        dhcp_relay = self.configuration[self.current_context]['dhcp_relay']
                    
                    dhcp_relay['address'] = [self.dhcp_line[3]]
                #BGP
                if re.match('\s\sneighbor', line, re.VERBOSE):
                    self.bgp_peer = line.split()
                    if self.bgp_peer[2] == 'external':
                        self.bgp_peer_address = self.bgp_peer[1]
                elif (self.bgp_peer_address) and (len(line) - len(line.lstrip()) > 2):
                    ##TODO: 
                    pass
                else:
                    self.bgp_peer_address = None


    def parsePort(self, cfg):
        """ Parse physical ports and get bw and bind status
        """
        self.fh = open(cfg,"r")
        self.config = self.fh.readlines()
        self.current_port = None
        self.current_slot = None

        for line in self.config:
            b = re.match('port\sethernet\s(?P<slot>[0-9])\/(?P<port>[0-9])', line, re.VERBOSE)
            if b is not None:
                self.current_port = b.group('slot')
                self.current_slot = b.group('port')
            elif (self.current_port) and (self.current_slot) and (len(line) - len(line.lstrip()) > 0):
                if re.match('\sdot1q', line, re.VERBOSE):
                    #pvc
                    self.current_intf = None
                    self.current_context = None 
                elif re.match('\s\sbind\sinterface', line, re.VERBOSE):
                    #bind interface
                    self.current_intf = line.split()[2]
                    self.current_context = line.split()[3]
                    self.configuration[self.current_context]['interface'][self.current_intf]['binded'] = True
                elif re.match('\s\sl2vpn', line, re.VERBOSE):
                    #l2vpn eompls
                    #print line.split()
                    pass
                elif re.match('\s\sqos', line, re.VERBOSE):
                    #qos policys
                    b = re.findall(r'([0-9]?[0-9]?[0-9])',line.split()[3], re.VERBOSE)
                    if (len(b) > 0) and (self.current_intf):
                        self.configuration[self.current_context]['interface'][self.current_intf]['bw'] = b[0]
            else:
                ##print "port end"
                self.current_port = None
                self.current_port = None
    
                self.current_intf = None
                self.current_context = None 
   

    
    def printConfig(self): 
        for key in self.configuration:
            print ""
            print "Context: ", key
            if 'interface' in self.configuration[key]:
                print "interface"
                for tt in self.configuration[key]['interface']:
                    print "%s %s " % (tt, self.configuration[key]['interface'][tt])
                for aa in self.configuration[key]['routing']['connected']:
                    pass
                    #print "connected list"
                    #print "%s %s" % (self.configuration[key]['routing']['connected'][aa], aa)
            if 'routing' in self.configuration[key]:
                print "routing"
                if 'static' in self.configuration[key]['routing']:
                    for bb in self.configuration[key]['routing']['static']:
                        
                        if 'nexthop' in self.configuration[key]['routing']['static'][bb]:
                            nhop = self.configuration[key]['routing']['static'][bb]['nexthop']
                            if not nhop is None:
                                rnode = self.configuration[key]['routing']['connected'].search_best(nhop)
                                if rnode is not None:
                                    parent_intf = rnode.data['parent_intf']
                                    print bb + " -> " + nhop + " (" + parent_intf + ")"
                                else:
                                    print "ROUTE NOT IN CONNECTED:", bb, nhop
                        else:
                            print "DEBUG ", self.configuration[key]['routing']['static']

            if 'dhcp_relay' in self.configuration[key]:
                print "DHCP"
                for kk in self.configuration[key]['dhcp_relay']:
                    print self.configuration[key]['dhcp_relay'][kk]



    def listContext(self):
        """ print our contexts and rd
        """
        for context in self.configuration:
            if 'vpn_rd' in self.configuration[context]:
                print "%s = %s " % (context, self.configuration[context]['vpn_rd'])
            else:
                print "%s " % (context)
    
    def printCiscoConfig(self):
        """ haxx for gbg80 crasch
        """
        self.all_context = []
        for context in self.configuration:
            if 'dhcp_relay' in self.configuration[context]:
                for int in self.configuration[context]['interface']:
                    
                    interface = self.configuration[context]['interface'][int]
                    if 'dhcp_relay' in interface and  'pri_ipv4' in interface:
                        #print self.configuration[context]['interface'][int]
                        if 'vlan_id' in interface:
                            self.all_context.append(self.configuration[context]['vpn_rd'])
                            print "int Te9/1." + interface['vlan_id']
                            print "encap dot1q pvc", interface['vlan_id']
                            print "description", interface['description']
                            print "ip vrf forwarding 1257:" + self.configuration[context]['vpn_rd'].strip()
                            print "ip address", interface[int]['pri_ipv4']
                            if 'sec_ipv4' in interface:
                                print "ip address " + interface['sec_ipv4'][0] +" secondary"
                            if 'dhcp_relay' in self.configuration[context]:
                                for adr in self.configuration[context]['dhcp_relay']['address']:
                                    print "ip helper-address " + adr
                            if 'routing' in self.configuration[context]:
                                if 'static' in self.configuration[context]['routing']:
                                    for bb in self.configuration[context]['routing']['static']:

                                        if 'nexthop' in self.configuration[context]['routing']['static'][bb]:
                                            nhop = self.configuration[context]['routing']['static'][bb]['nexthop']
                                            if not nhop is None:
                                                rnode = self.configuration[context]['routing']['connected'].search_best(nhop)
                                                if rnode is not None:
                                                    parent_intf = rnode.data['parent_intf']
                                                    if parent_intf == self.configuration[context]['interface'][int]:
                                                        print bb + " -> " + nhop + " (" + parent_intf + ")"
                                                else:
                                                    print "INVALID ROUTE:", bb, nhop
                                        else:
                                            pass
                                            #print "DEBUG ", self.configuration[context]['routing']['static']
 
                        print ""
        list(set(self.all_context))
        for rd in list(set(self.all_context)):
            print "/home/staff/fredsod0/bin/make.vpn " + rd + " gbg-pe-1"
        print " "
        print " "



    def printGBG80(self):
        """hax for gbg80 crash
        """

        for context in self.configuration:
            if 'dhcp_relay' in self.configuration[context]:
                for int in self.configuration[context]['interface']:
                    if 'dhcp_relay' in self.configuration[context]['interface'][int] and  'pri_ipv4' in self.configuration[context]['interface'][int]:
                        #print self.configuration[context]['interface'][int]
                        if 'vlan_id' in self.configuration[context]['interface'][int]:
                            print "context " + context
                            print "no interface " + int         
                



class ParseCisco():
    """ Parse cisco config
    """
    def __init__(self, cfg):

        self.configuration = {} 
        self.configfile = cfg
        self._parseVRF(cfg)


    def _parseVRF(self,cfg):
        """Get all vrf 
        """
        self.fh = open(cfg,"r")
        self.config = self.fh.readlines()
        self.current_context = None
        self.text = None

        for line in self.config:
            #ip vrf 1257:1274                                    
            if re.match('ip\svrf\s[0-9]+:[0-9]+', line, re.VERBOSE):
                self.vrf = line.split()[2]
                self.configuration[self.vrf] = None        



    def printConfig(self):

        for vrf in self.configuration:
            print vrf




if __name__ == '__main__':
    import logging
    import logging.handlers
    logger = logging.getLogger()
    log_format = "%(levelname)-8s %(message)s"
    # log to stdout
    log_stream = logging.StreamHandler()
    log_stream.setFormatter(logging.Formatter("%(asctime)s: " + log_format))
    logger.addHandler(log_stream)
    
    import optparse
    parser = optparse.OptionParser()
    ##
    parser.add_option("-f", "--from-router", dest = "from_router", help = "From Router")
    parser.add_option("-t", "--to-router", dest = "to_router", help = "To Router")
    parser.add_option("-i", "--interface", dest = "to_int", help = "Interface on destination router")
    parser.add_option("--list-context", action = "store_true",  dest = "listcontext", help = "List context missing on destination Router")
    parser.add_option("--list-vlan", action = "store_true",  dest = "listvlan", help = "List all vlan and ")
    parser.add_option("-o", "--output-file", dest = "output-file", help = "Output conf to file")

    ##
    
    (options, args) = parser.parse_args()
    
    if options.from_router:
        pass
    else:
        print >> sys.stderr, "You must provide exactly one router"
        sys.exit(1)

    #from_router config
    configFile = "/misc/tele2.net/config/all/" + options.from_router + ".tele2.net"
    
    if options.to_router:
        destConfigFile = "/misc/tele2.net/config/all/" + options.to_router + ".tele2.net"
    
    
    from_router = ParseRedback(configFile)
    to_router = ParseCisco(destConfigFile)
   

    if options.listcontext:
        fromrouter.listContext() 
    
    #fromrouter.printConfig()
    #torouter.printConfig()

    #compare config
    
    def compareVRF(): 
        #compare vrf
        specialVRF = {
            '10001': 'sipnet',
            '210': 'SHDSL',
            '100': 'mpls_monitor',
            '532': 'sipnet',
            '504': 'sipnet',
            '250': 't2v-ems'
            }
        print ""
        print "Checking for missing vrf in " + options.torouter
        print ""
        for vpn in fromrouter.configuration:
            if (fromrouter.configuration[vpn]['vpn_rd'] is not None) and (len(fromrouter.configuration[vpn]['interface']) > 0):
                rd = '1257:' + fromrouter.configuration[vpn]['vpn_rd']
                if not rd in torouter.configuration:
                    if (fromrouter.configuration[vpn]['vpn_rd'] in specialVRF) or (len(fromrouter.configuration[vpn]['vpn_rd']) <> 4): 
                        print '1257:'+fromrouter.configuration[vpn]['vpn_rd'] + " SPECIAL VRF, conf manually"
                    else:
                        print "cpush -a --ios-file bgp-vpn-vrf_ios -v VPN-ID="+fromrouter.configuration[vpn]['vpn_rd']+" -v VRF-DESCRIPTION='' -j " + options.torouter



