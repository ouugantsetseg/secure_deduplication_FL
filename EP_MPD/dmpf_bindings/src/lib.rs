use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use dmpf::{
    DpfDmpf, 
    Dmpf, 
    DmpfKey as DmpfKeyTrait, 
    DmpfSession, 
    dpf::{DpfDmpfKey, DpfDmpfSession}, 
    batch_code::{BatchCodeDmpf, BatchCodeDmpfKey, BatchCodeDmpfSession},
    okvs::{OkvsDmpf, OkvsDmpfKey},
    EmptySession,
    EpsilonPercent,
    utils::Node
};
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

/// Internal enum to hold different DMPF key types
enum DmpfKeyImpl {
    Dpf(DpfDmpfKey<Node>),
    BatchCode(BatchCodeDmpfKey<Node>),
    Okvs49(OkvsDmpfKey<1, 49, Node>),   // For ≤ 1K points
    Okvs56(OkvsDmpfKey<1, 56, Node>),   // For 1K-16K points
    Okvs59(OkvsDmpfKey<1, 59, Node>),   // For > 16K points
}

/// Python wrapper for DMPF key
#[pyclass]
struct DmpfKey {
    key: DmpfKeyImpl,
}

#[pymethods]
impl DmpfKey {
    /// Evaluate the DMPF key at a given input
    fn eval(&self, input: u128) -> PyResult<u128> {
        let mut output = Node::default();
        
        match &self.key {
            DmpfKeyImpl::Dpf(dpf_key) => {
                let mut session = DpfDmpfSession::get_session(dpf_key.point_count(), dpf_key.input_length());
                let input_length = dpf_key.input_length();
                let encoded_input = input << (128 - input_length);
                dpf_key.eval_with_session(&encoded_input, &mut output, &mut session);
            }
            DmpfKeyImpl::BatchCode(batch_key) => {
                let mut session = BatchCodeDmpfSession::get_session(batch_key.point_count(), batch_key.input_length());
                let input_length = batch_key.input_length();
                let encoded_input = input << (128 - input_length);
                batch_key.eval_with_session(&encoded_input, &mut output, &mut session);
            }
            DmpfKeyImpl::Okvs49(okvs_key) => {
                let mut session = EmptySession::get_session(okvs_key.point_count(), okvs_key.input_length());
                let input_length = okvs_key.input_length();
                let encoded_input = input << (128 - input_length);
                okvs_key.eval_with_session(&encoded_input, &mut output, &mut session);
            }
            DmpfKeyImpl::Okvs56(okvs_key) => {
                let mut session = EmptySession::get_session(okvs_key.point_count(), okvs_key.input_length());
                let input_length = okvs_key.input_length();
                let encoded_input = input << (128 - input_length);
                okvs_key.eval_with_session(&encoded_input, &mut output, &mut session);
            }
            DmpfKeyImpl::Okvs59(okvs_key) => {
                let mut session = EmptySession::get_session(okvs_key.point_count(), okvs_key.input_length());
                let input_length = okvs_key.input_length();
                let encoded_input = input << (128 - input_length);
                okvs_key.eval_with_session(&encoded_input, &mut output, &mut session);
            }
        }
        
        // Convert Node to u128 using From trait
        Ok(output.into())
    }
}

/// Python wrapper for DMPF generator
#[pyclass]
struct DmpfGenerator {
    use_batch_code: bool,
}

#[pymethods]
impl DmpfGenerator {
    /// Create a new DMPF generator
    /// 
    /// Args:
    ///     use_batch_code: Deprecated. Use dmpf_type instead.
    ///                     If True, uses BatchCodeDmpf. If False, auto-selects.
    #[new]
    #[pyo3(signature = (use_batch_code=None))]
    fn new(use_batch_code: Option<bool>) -> Self {
        DmpfGenerator {
            use_batch_code: use_batch_code.unwrap_or(false),
        }
    }

    /// Generate DMPF keys for a set of (input, output) points
    /// 
    /// Args:
    ///     input_length: Number of bits in the input domain
    ///     points: List of tuples (input: int, output: int)
    /// 
    /// Returns:
    ///     Tuple of (key_0, key_1)
    fn generate_keys(
        &self,
        input_length: usize,
        points: Vec<(u128, u128)>,
    ) -> PyResult<(DmpfKey, DmpfKey)> {
        let num_points = points.len();
        
        // Auto-select DMPF type based on point count
        // OKVS-DMPF: Best for 5K-500K points (MUCH faster evaluation)
        // BatchCode-DMPF: Only for massive datasets (≥500K) where key size matters more than eval speed
        let use_okvs = num_points >= 5000 && num_points < 5000000 && !self.use_batch_code;
        let use_batch = self.use_batch_code || num_points >= 5000000;        // Convert u128 outputs to Node using From trait
        // Also encode inputs: shift bits to MSB side
        let mut node_points: Vec<(u128, Node)> = points
            .into_iter()
            .map(|(input, output)| {
                let encoded_input = input << (128 - input_length);
                (encoded_input, Node::from(output))
            })
            .collect();

        // OKVS requires sorted AND UNIQUE inputs
        if use_okvs {
            node_points.sort_by_key(|(input, _)| *input);
            // Remove duplicates by keeping only unique inputs (last value wins)
            node_points.dedup_by_key(|(input, _)| *input);
        }

        // Generate keys using a cryptographic random number generator with random seed
        use rand::RngCore;
        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);
        let mut rng = ChaCha8Rng::from_seed(seed);
        
        if use_okvs {
            // Use OkvsDmpf with appropriate W parameter based on point count
            // W=49 for ≤1K, W=56 for ≤16K, W=59 for >16K
            let batch_size = 8;
            let epsilon = EpsilonPercent::Hundred;
            
            if num_points <= 1024 {
                let generator = OkvsDmpf::<1, 49, Node>::new(epsilon, batch_size);
                match generator.try_gen(input_length, &node_points, &mut rng) {
                    Some((key_0, key_1)) => {
                        return Ok((
                            DmpfKey { key: DmpfKeyImpl::Okvs49(key_0) },
                            DmpfKey { key: DmpfKeyImpl::Okvs49(key_1) },
                        ));
                    }
                    None => return Err(PyValueError::new_err("Failed to generate OKVS-49 DMPF keys")),
                }
            } else if num_points <= 16384 {
                let generator = OkvsDmpf::<1, 56, Node>::new(epsilon, batch_size);
                match generator.try_gen(input_length, &node_points, &mut rng) {
                    Some((key_0, key_1)) => {
                        return Ok((
                            DmpfKey { key: DmpfKeyImpl::Okvs56(key_0) },
                            DmpfKey { key: DmpfKeyImpl::Okvs56(key_1) },
                        ));
                    }
                    None => return Err(PyValueError::new_err("Failed to generate OKVS-56 DMPF keys")),
                }
            } else {
                let generator = OkvsDmpf::<1, 59, Node>::new(epsilon, batch_size);
                match generator.try_gen(input_length, &node_points, &mut rng) {
                    Some((key_0, key_1)) => {
                        return Ok((
                            DmpfKey { key: DmpfKeyImpl::Okvs59(key_0) },
                            DmpfKey { key: DmpfKeyImpl::Okvs59(key_1) },
                        ));
                    }
                    None => return Err(PyValueError::new_err("Failed to generate OKVS-59 DMPF keys")),
                }
            }
        }
        
        if use_batch {
            // Use BatchCodeDmpf for very large datasets (if explicitly requested)
            let generator = BatchCodeDmpf::new();
            match generator.try_gen(input_length, &node_points, &mut rng) {
                Some((key_0, key_1)) => {
                    Ok((
                        DmpfKey { key: DmpfKeyImpl::BatchCode(key_0) },
                        DmpfKey { key: DmpfKeyImpl::BatchCode(key_1) },
                    ))
                }
                None => Err(PyValueError::new_err("Failed to generate BatchCode DMPF keys")),
            }
        } else {
            // Use DpfDmpf for small datasets (< 1K points)
            let generator = DpfDmpf::new();
            match generator.try_gen(input_length, &node_points, &mut rng) {
                Some((key_0, key_1)) => {
                    Ok((
                        DmpfKey { key: DmpfKeyImpl::Dpf(key_0) },
                        DmpfKey { key: DmpfKeyImpl::Dpf(key_1) },
                    ))
                }
                None => Err(PyValueError::new_err("Failed to generate DPF DMPF keys")),
            }
        }
    }
}

/// Python module for DMPF bindings
#[pymodule]
fn dmpf_py(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<DmpfGenerator>()?;
    m.add_class::<DmpfKey>()?;
    Ok(())
}
