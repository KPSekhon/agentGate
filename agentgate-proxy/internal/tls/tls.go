package tls

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"
)

type Config struct {
	CertFile string
	KeyFile  string
	ClientCA string
}

func (c *Config) Enabled() bool {
	return c.CertFile != "" && c.KeyFile != ""
}

func (c *Config) MutualTLSEnabled() bool {
	return c.Enabled() && c.ClientCA != ""
}

func (c *Config) Build() (*tls.Config, error) {
	if !c.Enabled() {
		return nil, nil
	}

	cert, err := tls.LoadX509KeyPair(c.CertFile, c.KeyFile)
	if err != nil {
		return nil, fmt.Errorf("loading TLS keypair: %w", err)
	}

	tlsCfg := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS13,
	}

	if c.ClientCA != "" {
		caCert, err := os.ReadFile(c.ClientCA)
		if err != nil {
			return nil, fmt.Errorf("loading client CA: %w", err)
		}
		pool := x509.NewCertPool()
		if !pool.AppendCertsFromPEM(caCert) {
			return nil, fmt.Errorf("failed to parse client CA certificate")
		}
		tlsCfg.ClientCAs = pool
		tlsCfg.ClientAuth = tls.RequireAndVerifyClientCert
	}

	return tlsCfg, nil
}
