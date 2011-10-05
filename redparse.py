#!/usr/bin/python
# vim: et ts=4 :
import sys
import re

# a dict of VRF-IDs that we should ignore, only the keys are interesting
ignore_vrfs = {
        '100': 'mpls_monitor',
        '210': 'SHDSL',
        '250': 't2v-ems',
        '504': 'sipnet',
        '532': 'sipnet',
        '10001': 'sipnet'
        }


class Config:
    def __init__(self, config):
        self.config = config
        self.vrfs = {}
        self._parse_shite()


    def _parse_shite(self):
        for vrf_name in self.config:
            vrf = self.config[vrf_name]
            if type(vrf) == dict and 'vpn_id' in vrf:
                if vrf['vpn_id'] is not None:
                    self.vrfs[vrf['vpn_id']] = vrf
                else:
                    self.vrfs[''] = vrf



    def _cidr_to_netmask(self, bits):
        """ Convert CIDR bits to netmask 
        """
        netmask = ''
        for i in range(4):
            if i:
                netmask += '.'
            if bits >= 8:
                netmask += '%d' % (2**8-1)
                bits -= 8
            else:
                netmask += '%d' % (256-2**(8-bits))
                bits = 0
        return netmask


    def cmp_vrfs(self, other):
        """ Compare this Config with another one and return differing VRF IDs

            First list returned is vrfs unique to this Config while the second
            returned list contains vrfs unique to the other config
        """
        my_vrfs = set(self.vrfs)
        other_vrfs = set(other.vrfs)
        return my_vrfs - other_vrfs, other_vrfs - my_vrfs


    def output_config(self, intf):
        """ Output config 
		Output should look like this
		interface tenGigabitEthernet 9/2.2000
		 ecapsulation dot1q 2000
		 ip vrf forwarding 1257:1700
		 ip address 130.244.105.0 255.255.255.254
		 service-policy QOS-VPN-SHAPE input  [external script?]
		 service-policy QOS-VPN-SHAPE output [external script]
		 no ip redirects
         no ip proxy-arp
		 ip helper-address 1.1.1.1

		ip route vrf 1257:1700 10.10.10 255.255.255.0 9/2.2000 130.244.105.1

        """
        self.output_int = intf
        self.output = []
        for vrf_name in self.config:
            if vrf_name == 'ADSL': # Adsl nono!
                continue
            vrf = self.config[vrf_name]
            self.output = []
            if 'vpn_id' in vrf:
			    current_vrf_id = vrf['vpn_id']
            if 'interface' in vrf:
                for port in vrf['interface']:
                    intf = vrf['interface'][port]
                    if 'binded' in intf and 'pri_ipv4' in intf:
                        
                        self.current_intf = "te" + self.output_int +"." + intf['vlan_id']
                        self.output.append("interface " +self.current_intf)
                        self.output.append(" encapsulation dot1q " + intf['vlan_id'])
                        if 'description' in intf:
                            self.output.append(" description " + intf['description'])
                        if current_vrf_id:
                            self.output.append(" ip vrf forwarding 1257:" + current_vrf_id)
                        self.output.append(" ip address " + intf['pri_ipv4'].split('/')[0] + " " + self._cidr_to_netmask(int(intf['pri_ipv4'].split('/')[1])))
                        if 'sec_ipv4' in intf:
                            for sec_adr in intf['sec_ipv4']:
                                self.output.append(" ip address " + sec_adr.split('/')[0] + " " + self._cidr_to_netmask(int(sec_adr.split('/')[1])) + " secondary")
                        if 'dhcp_relay' in vrf:
                            for adr in vrf['dhcp_relay']['address']:
                                self.output.append(" ip-helper address " + adr)
                        if 'routing' in vrf:
                            # static routing
                            if 'static' in vrf['routing']:
                                stat = vrf['routing']['static']
                                for net in stat:
                                    if 'nexthop' in stat[net] :
                                        nhop = stat[net]['nexthop']
                                        if nhop is not None:
                                            rnode = vrf['routing']['connected'].search_best(nhop)
                                            if rnode is not None:
                                                parent_intf = rnode.data['parent_intf']
                                                if parent_intf == port:
                                                    if current_vrf_id:
                                                        self.output.append("ip route vrf 1257:" +current_vrf_id +" " + net.split('/')[0] + " " + self._cidr_to_netmask(int(net.split('/')[1])) +" " + self.current_intf + " " + nhop )
                                                    else:
                                                        self.output.append("ip route " + net.split('/')[0] + " " + self._cidr_to_netmask(int(net.split('/')[1])) +" " +  self.current_intf + " " + nhop )
                                            else:
                                                self.output.append("Cant find nexthop for " + net)
                                        else:
                                            pass
                                            #self.output.append("---------- INVALID " + net)
                            # BGP
                            if 'bgp' in vrf['routing']:
                                for peer in vrf['routing']['bgp']:
                                    rnode = vrf['routing']['connected'].search_best(peer)
                                    if rnode is not None:
                                        parent_intf = rnode.data['parent_intf']
                                        if parent_intf == port:
                                            self.output.append("--found som bgp :) "+  peer)
            
            print ""
            print vrf_name
            for i in self.output:
                print i




		


class ParseRedback(object):
    """
    """
    def __init__(self, cfg):


        self.configuration = {}
        """
        self.configuration
            skanet-in-public
                vpn-id = 1004
                raw_config = "confocnfongconf"
                interfaces
                    ge2-2.1212
                        vlan = 1212
                        pri_ipv4 = 1.1.1.1/24
                        sec_ipv4 = [2.2.2.2/24]
                        description = "IP-PORT232312,fsdfsd, test"
                        dhcp_relay = true
                        bw = 10
                        binded = True
                    ge2-2.1414
                        vlan = 1414
                        pri_ipv4 = 4.4.4.4/24
                        sec_iv4 = [43.2.2.2/24, 23.23.23.23/25]
                        description = "IP-PORT23232,2222 Goteborg"
                routing
                    connected (haxx ip type)
                        1.1.1.1/24  = ge2-2.1212
                        2.2.2.2/24  = ge2-2.1212
                        4.4.4.4/24  = ge2-2.1414
                        43.2.2.2/24 = ge2-2.1414
                        23.23.23.23/25  = ge2-2.1414
                    static
                        0.0.0.0/0
                            oif = ge1/1
                            nhop = 10.10.101.1
                        10.2.3.3/24
                            oif = None
                            nhop = 1.1.1.1
                    bgp
                        peer_adr = 130.244.0.1
                        description = "IP-PORT23232, fsdfsfsd"
                        remote-as = 65000
                        route-map_in = secondary
                        route-map_out = None

            dhcp_relay
                address = [1.1.1.1,2.2.2.2]

        """


        self.configfile = cfg       
        self._getContextConfig(self.configfile) 
        self._parseContextConfig()
        self.parsePort(self.configfile)
    
    
    def _getContextConfig(self, cfg):
        """ Parse config and store contextconfig and RD
        """
        self.fh = open(cfg, "r")
        self.config = self.fh.readlines()
        self.current_context = None
        self.text = None
        
        for line in self.config:
            m = re.match('context\s(?P<context_name>[^ ]+)(\svpn-rd\s.*:(?P<vpn_id>[0-9]+))?', line)
            n = re.match('.*(^!\s\*\*\sEnd\sContext\s\*\*)', line, re.VERBOSE)
            if n is not None:
                self.configuration[self.current_context]['raw_config'] = self.text
            elif m is not None:
                if self.current_context:
                    self.configuration[self.current_context]['raw_config'] = self.text

                if m.group('context_name') is None:
                    raise InputError("context fuckedup? " + str(self.line))

                self.current_context = m.group('context_name').strip()
                self.configuration[self.current_context] = {}
                self.configuration[self.current_context]['vpn_id'] = m.group('vpn_id')
                self.text = line 
            elif not re.match("^!", line):
                if self.current_context:
                    self.text += line

    

    def _parseContextConfig(self):
        """ Parse config and find useful stuff
        """
        
        self.parent_intf = None
        self.bgp_peer = None
        import radix
        
        for self.current_context in self.configuration:
            self.config = self.configuration[self.current_context]['raw_config'].split('\n')
            self.configuration[self.current_context]['interface'] = {}
            interface= self.configuration[self.current_context]['interface']
            self.configuration[self.current_context]['routing'] = {}
            routing = self.configuration[self.current_context]['routing']
            self.configuration[self.current_context]['routing']['connected'] = radix.Radix()
            connected = self.configuration[self.current_context]['routing']['connected']
        
            #find interfaces and attributes for them
            for line in self.config:
                #interface
                if re.match('\sinterface .*GE', line, re.VERBOSE):
                    if re.match('.*GE', line.split()[1]):
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
                if re.match(' ip route', line):
                    self.route_line = line.split()
                    #first route
                    if not 'static' in  routing:
                        routing['static'] = {}
                        static  = routing['static'] 
                    
                    static[self.route_line[2]] = {}
                    
                    if self.route_line[3] == "context":
                        static[self.route_line[2]]['nexthop'] = None
                    elif self.route_line[3] == "null0":
                        static[self.route_line[2]]['nexthop'] = None
                    elif len(self.route_line[3].split('.')) != 4:
                        #nexthop is a interface?
                        static[self.route_line[2]]['oif'] = self.route_line[3]
                    else:
                        # Look if nexthop is in our connected dict
                        rnode = connected.search_best(self.route_line[3])
                        if rnode is not None:
                            parent_intf = rnode.data['parent_intf']
                            static[self.route_line[2]]['nexthop'] = self.route_line[3]
                        else:
                            #remove the prefix
                            static.pop(self.route_line[2])
                
                #DHCP relay
                if re.match(' dhcp relay server', line):
                    self.dhcp_line = line.split()
                    if not 'dhcp_relay' in self.configuration[self.current_context]:
                        self.configuration[self.current_context]['dhcp_relay'] = {}
                        dhcp_relay = self.configuration[self.current_context]['dhcp_relay']
                    
                    dhcp_relay['address'] = [self.dhcp_line[3]]
                #BGP
                if re.match('  neighbor', line):
                    if not 'bgp' in routing:
                        routing['bgp'] = {}
                    self.bgp_peer = line.split()[1]
                    routing['bgp'][self.bgp_peer] = {}
                    peer = routing['bgp'][self.bgp_peer]
                elif (self.bgp_peer) and (len(line) - len(line.lstrip()) > 2):
                    # TODO: fix this shite! :)
                    if re.match(' {4,5}remote-as', line):
                        peer['remote-as'] = line.split()[1]
                    if re.match('    description', line):
                        peer['description'] = line.lstrip(' description')
                    if re.match('      route-map', line):
                        if line.split()[2] == 'in':
                            #route-map in
                            peer['route-map_in'] = line.split()[1]
                        elif line.split()[2] == 'out':
                            #route-map out
                            peer['route-map_out'] = line.split()[1]

                else:
                    self.bgp_peer = None
     
    

    def parsePort(self, cfg):
        """ Parse physical ports and get bw and bind status
        """
        self.fh = open(cfg, "r")
        self.config = self.fh.readlines()
        self.current_port = None
        self.current_slot = None

        for line in self.config:
            b = re.match('port\sethernet\s(?P<slot>[0-9])\/(?P<port>[0-9])', line, re.VERBOSE)
            if b is not None:
                self.current_port = b.group('slot')
                self.current_slot = b.group('port')
            elif self.current_port and self.current_slot and len(line) - len(line.lstrip()) > 0:
                if re.match('\sdot1q', line):
                    # pvc
                    self.current_intf = None
                    self.current_context = None 
                elif re.match('\s\sbind\sinterface', line):
                    # bind interface
                    self.current_intf = line.split()[2]
                    self.current_context = line.split()[3]
                    self.configuration[self.current_context]['interface'][self.current_intf]['binded'] = True
                elif re.match('\s\sl2vpn', line):
                    # l2vpn eompls
                    # TODO: handle l2vpn, ie EoMPLS
                    #print line.split()
                    pass
                elif re.match('\s{2}qos policy (policing|queueing)', line):
                    # qos policys, examples:
                    # qos policy queuing qosout-100Mbps-Real-time
                    # qos policy policing 10mbps-voice-in-mittmedia-service acl-counters
                    b = re.search(r'([0-9]+)', line.split()[3])
                    if b is not None and self.current_intf:
                        self.configuration[self.current_context]['interface'][self.current_intf]['bw'] = b.group(0)

            else:
                # end of port configuration
                self.current_port = None
                self.current_port = None
    
                self.current_intf = None
                self.current_context = None 
   


    def listContext(self):
        """ print our contexts and rd
        """
        for context in self.configuration:
            if 'vpn_id' in self.configuration[context]:
                print "%s = %s " % (context, self.configuration[context]['vpn_id'])
            else:
                print "%s " % (context)
    


class ParseCisco():
    """ Parse cisco config
    """
    def __init__(self, cfg):
        self.fh = open(cfg, "r")
        self.config = self.fh.readlines()

        self.configuration = {} 
        self.configfile = cfg
        self.es_ports = {}
        self._parseVRF(cfg)
        self._find_ES_ports()


    def _parseVRF(self,cfg):
        """ Get all VRFs
        """
        self.current_context = None
        self.text = None

        for line in self.config:
            #ip vrf 1257:1274
            rem = re.match('ip vrf (.+)', line)
            if rem is not None:
                self.vrf = line.split()[2]
                self.current_context = rem.group(1).strip()
                self.configuration[self.current_context] = {}

            if self.current_context is not None:
                if re.match(' rd ', line):
                    # rd 1.3.3.7:1234
                    rd = line.split()[1].strip()
                    vpn_id = line.split(':')[1].strip()
                    self.configuration[self.vrf]['vpn_id'] = vpn_id



    def _find_ES_ports(self):
        es_modules = {}

        for line in self.config:
            rem = re.match('!Slot ([0-9]+): .*ES\+', line)
            if rem is not None:
                es_modules[rem.group(1)] = True

        for line in self.config:
            rem = re.match('interface (?P<interface>(?P<if_type>[A-Za-z]+)(?P<slot>[0-9]+)/(?P<port>[0-9]+)(\.(?P<sub_if>[0-9]+))?)', line)
            if rem is not None:
                if rem.group('slot') in es_modules:
                    port = rem.group('slot') + '/' + rem.group('port')
                    vlan = rem.group('sub_if')

                    if port not in self.es_ports:
                        self.es_ports[port] = {}
                    self.es_ports[port][vlan] = True


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
    parser.add_option("--print-conf", action = "store_true", help = "Print config")
    parser.add_option("--cmp-vrfs", action = "store_true", help = "Compare VRFs")
    parser.add_option('--check-vlan', action = "store_true", help = "Check if there are VLAN collisions on the destination router/port")
    parser.add_option("-f", "--from-router", dest = "from_router", help = "From Router")
    parser.add_option("-t", "--to-router", dest = "to_router", help = "To Router")
    parser.add_option("-i", "--interface", dest = "to_int", help = "Interface on destination router")
    parser.add_option("-o", "--output-file", dest = "output-file", help = "Output conf to file")

    ##
    
    (options, args) = parser.parse_args()
    
    if options.from_router:
        pass
    else:
        print >> sys.stderr, "You must provide exactly one router"
        sys.exit(1)

    #from_router config
    configFile = "/misc/tele2.net/config/all/" + options.from_router.lower() + ".tele2.net"
    
    if options.to_router:
        destConfigFile = "/misc/tele2.net/config/all/" + options.to_router.lower() + ".tele2.net"
    
    
    from_router = ParseRedback(configFile)
    to_router = ParseCisco(destConfigFile)

    from_cfg = Config(from_router.configuration)
    to_cfg = Config(to_router.configuration)

    # Print config
    if options.print_conf:
        if options.to_int is None:
            print >> sys.stderr, "Please specify the 'destination interface'"
            sys.exit(1)
        from_cfg.output_config(options.to_int)


    # compare VRFs to determine whether we need to add anything
    if options.cmp_vrfs:
        ignore = set(ignore_vrfs)
        l1, l2 = from_cfg.cmp_vrfs(to_cfg)
        ignored = l1.intersection(ignore)
        print "We need to create the following VRFS in", options.to_router
        # ignore the "global" vrf, which is stored as ''
        l1 = l1 - set(('',))
        l1 = l1 - ignore
        for vrf in sorted(l1, key=int):
            print " ", vrf

        print "The following VRFs were ignored and need to be handled manually:"
        for vrf in ignored:
            print " ", vrf

    # check for VLAN collisions
    if options.check_vlan:
        if options.to_int is None:
            print >> sys.stderr, "Please specify the 'destination interface'"
            sys.exit(1)

        if options.to_int not in to_router.es_ports:
            print >> sys.stderr, "Destination port does not appear to be an ES+!"
            sys.exit(1)

        from_vlans = {}
        for vrf_name in from_router.configuration:
            vrf = from_router.configuration[vrf_name]
            for if_name in vrf['interface']:
                interface = vrf['interface'][if_name]
                if 'binded' not in interface:
                    continue
                if 'vlan_id' not in interface:
                    vlan_id = 0
                else:
                    vlan_id = interface['vlan_id']
                from_vlans[vlan_id] = interface
        res = set(from_vlans).intersection(set(to_router.es_ports[options.to_int]))
        print "Colliding VLANs:", res


    def compareVRF(): 
        #compare vrf
        print ""
        print "Checking for missing vrf in " + options.torouter
        print ""
        for vpn in fromrouter.configuration:
            if (fromrouter.configuration[vpn]['vpn_id'] is not None) and (len(fromrouter.configuration[vpn]['interface']) > 0):
                rd = '1257:' + fromrouter.configuration[vpn]['vpn_id']
                if not rd in torouter.configuration:
                    if (fromrouter.configuration[vpn]['vpn_id'] in ignore_vrf) or (len(fromrouter.configuration[vpn]['vpn_id']) <> 4): 
                        print '1257:'+fromrouter.configuration[vpn]['vpn_id'] + " ignore_vrf VRF, conf manually"
                    else:
                        print "cpush -a --ios-file bgp-vpn-vrf_ios -v VPN-ID="+fromrouter.configuration[vpn]['vpn_id']+" -v VRF-DESCRIPTION='' -j " + options.torouter



