package failingtests

import "testing"

func TestOne(t *testing.T) {
	if One() != 2 {
		t.Fatal("one is not two")
	}
}
